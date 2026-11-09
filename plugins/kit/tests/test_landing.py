# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest>=8"]
# ///
"""Landing (D48): hub paths to main, projects/ to a goal branch, one tree.
Run: uv run --script plugins/kit/tests/test_landing.py"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from kitlib import landing, undo  # noqa: E402
from kitlib.common import KitError, git  # noqa: E402

ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x", "GIT_COMMITTER_NAME": "t",
       "GIT_COMMITTER_EMAIL": "t@x", "GIT_TERMINAL_PROMPT": "0"}


def sh(*argv: str, cwd: Path) -> str:
    out = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, env=ENV, check=True)
    return out.stdout.strip()


@pytest.fixture
def repos(tmp_path: Path) -> tuple[Path, Path]:
    origin = tmp_path / "origin.git"
    sh("git", "init", "-q", "--bare", "-b", "main", str(origin), cwd=tmp_path)
    ws = tmp_path / "ws"
    ws.mkdir()
    sh("git", "init", "-q", "-b", "main", cwd=ws)
    sh("git", "config", "user.name", "t", cwd=ws)
    sh("git", "config", "user.email", "t@x", cwd=ws)
    (ws / "README.md").write_text("# ws\n")
    (ws / "projects").mkdir()
    (ws / "projects" / "README.md").write_text("projects\n")
    sh("git", "add", "-A", cwd=ws)
    sh("git", "commit", "-q", "-m", "Start", cwd=ws)
    sh("git", "remote", "add", "origin", str(origin), cwd=ws)
    sh("git", "push", "-q", "-u", "origin", "main", cwd=ws)
    return ws, origin


def write(ws: Path, rel: str, text: str) -> None:
    p = ws / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def test_hub_only_lands_on_main(repos):
    ws, _ = repos
    write(ws, "docs/note.md", "hello\n")
    result = landing.land(ws, "Add a note")
    assert result["landed"] and "docs/note.md" in result["hub"] and not result["projects"]
    # A docs change also lands the OKF log and index the kit keeps (D60).
    assert {"docs/log.md", "docs/index.md"} <= set(result["hub"])
    assert sh("git", "log", "-1", "--format=%s", cwd=ws) == "Add a note"
    assert sh("git", "status", "--porcelain", cwd=ws) == ""


def test_project_lands_on_branch_not_main(repos):
    ws, _ = repos
    write(ws, "projects/app/.kit.json", '{"goal": "ship-app"}\n')
    write(ws, "projects/app/main.py", "print('hi')\n")
    write(ws, "goals/ship-app/README.md", "goal\n")
    head_before = sh("git", "rev-parse", "HEAD", cwd=ws)
    result = landing.land(ws, "First cut of the app")
    assert result["hub"] == ["goals/ship-app/README.md"]
    assert result["projects"][0]["branch"] == "goal/ship-app" and result["projects"][0]["committed"]
    # main moved only for the hub file; the branch holds the project files.
    assert "projects/app/main.py" not in sh("git", "ls-tree", "-r", "--name-only", "HEAD", cwd=ws)
    assert "projects/app/main.py" in sh("git", "ls-tree", "-r", "--name-only", "goal/ship-app", cwd=ws)
    assert sh("git", "rev-parse", "HEAD", cwd=ws) != head_before
    assert sh("git", "rev-parse", "--abbrev-ref", "HEAD", cwd=ws) == "main"
    # Working tree still has the project file; a second land is a no-op for it.
    assert (ws / "projects/app/main.py").exists()
    again = landing.land(ws, "Nothing new")
    assert again["landed"] is False or not again["projects"] or again["projects"][0]["committed"] is False


def test_second_land_adds_a_commit_on_the_branch(repos):
    ws, _ = repos
    write(ws, "projects/app/.kit.json", "{}\n")
    write(ws, "projects/app/a.py", "1\n")
    landing.land(ws, "one")
    write(ws, "projects/app/a.py", "2\n")
    write(ws, "projects/app/b.py", "b\n")
    landing.land(ws, "two")
    log = sh("git", "log", "--format=%s", "project/app", cwd=ws).splitlines()
    assert log[:2] == ["two", "one"]
    assert sh("git", "show", "project/app:projects/app/a.py", cwd=ws) == "2"


def test_deleted_project_file_is_removed_on_branch(repos):
    ws, _ = repos
    write(ws, "projects/app/.kit.json", "{}\n")
    write(ws, "projects/app/a.py", "1\n")
    write(ws, "projects/app/old.py", "old\n")
    landing.land(ws, "one")
    (ws / "projects/app/old.py").unlink()
    landing.land(ws, "drop old")
    assert "projects/app/old.py" not in sh("git", "ls-tree", "-r", "--name-only", "project/app", cwd=ws)


def test_secret_blocks_everything(repos):
    ws, _ = repos
    write(ws, "docs/ok.md", "fine\n")
    write(ws, "projects/app/config.py", 'TOKEN = "ghp_Zq8vL2mN4pR7sT1uW9xA3bC5dE6fG0hJkLmN"\n')
    with pytest.raises(KitError) as exc:
        landing.land(ws, "oops")
    assert "secret" in str(exc.value)
    assert sh("git", "log", "--format=%s", cwd=ws).splitlines() == ["Start"]
    assert sh("git", "branch", "--list", "project/app", cwd=ws) == ""


def test_sync_end_pushes_main_and_branch_and_opens_pr(repos):
    ws, origin = repos
    write(ws, "docs/n.md", "n\n")
    write(ws, "projects/app/.kit.json", '{"goal": "g"}\n')
    write(ws, "projects/app/a.py", "1\n")
    landing.land(ws, "work")
    opened = []

    def fake_open_pr(root, branch, project):
        opened.append((branch, project))
        return {"number": 7, "opened": True}

    report = landing.sync(ws, "end", open_pr=fake_open_pr)
    pushed = {p["branch"]: p["ok"] for p in report["pushed"]}
    assert pushed == {"main": True, "goal/g": True}
    assert opened == [("goal/g", "app")]
    assert sh("git", "rev-parse", "goal/g", cwd=ws) == sh("git", "--git-dir", str(origin), "rev-parse", "goal/g", cwd=ws)


def test_sync_start_after_remote_merge_lands_project_on_main(repos, tmp_path):
    ws, origin = repos
    write(ws, "projects/app/.kit.json", '{"goal": "g"}\n')
    write(ws, "projects/app/a.py", "1\n")
    landing.land(ws, "work")
    landing.sync(ws, "end", open_pr=None)
    # The caretaker (another clone) fixes a file on the branch and merges it into main.
    other = tmp_path / "other"
    sh("git", "clone", "-q", str(origin), str(other), cwd=tmp_path)
    sh("git", "config", "user.name", "c", cwd=other); sh("git", "config", "user.email", "c@x", cwd=other)
    sh("git", "checkout", "-q", "goal/g", cwd=other)
    (other / "projects/app/a.py").write_text("1  # fixed by caretaker\n")
    sh("git", "commit", "-q", "-am", "Fix lint", cwd=other)
    sh("git", "checkout", "-q", "main", cwd=other)
    sh("git", "merge", "-q", "--no-ff", "-m", "Merge goal/g", "goal/g", cwd=other)
    sh("git", "push", "-q", "origin", "main", ":goal/g", cwd=other)

    report = landing.sync(ws, "start", open_pr=None)
    assert any("landed on main" in n for n in report["notes"])
    assert (ws / "projects/app/a.py").read_text() == "1  # fixed by caretaker\n"
    assert sh("git", "status", "--porcelain", cwd=ws) == ""
    assert landing.landed_state(ws)["projects"] == {}
    assert sh("git", "branch", "--list", "goal/g", cwd=ws) == ""


def test_sync_start_picks_up_caretaker_commit_on_open_branch(repos, tmp_path):
    ws, origin = repos
    write(ws, "projects/app/.kit.json", '{"goal": "g"}\n')
    write(ws, "projects/app/a.py", "1\n")
    landing.land(ws, "work")
    landing.sync(ws, "end", open_pr=None)
    other = tmp_path / "other"
    sh("git", "clone", "-q", str(origin), str(other), cwd=tmp_path)
    sh("git", "config", "user.name", "c", cwd=other); sh("git", "config", "user.email", "c@x", cwd=other)
    sh("git", "checkout", "-q", "goal/g", cwd=other)
    (other / "projects/app/a.py").write_text("2\n")
    sh("git", "commit", "-q", "-am", "Fix", cwd=other)
    sh("git", "push", "-q", "origin", "goal/g", cwd=other)

    landing.sync(ws, "start", open_pr=None)
    assert (ws / "projects/app/a.py").read_text() == "2\n"
    assert sh("git", "rev-parse", "goal/g", cwd=ws) == sh("git", "rev-parse", "origin/goal/g", cwd=ws)
    # And a further local edit lands on top of the caretaker's commit, not over it.
    (ws / "projects/app/a.py").write_text("3\n")
    landing.land(ws, "more")
    assert sh("git", "log", "--format=%s", "goal/g", cwd=ws).splitlines()[:3] == ["more", "Fix", "work"]


def _caretaker_clone(tmp_path, origin):
    other = tmp_path / "other"
    sh("git", "clone", "-q", str(origin), str(other), cwd=tmp_path)
    sh("git", "config", "user.name", "c", cwd=other); sh("git", "config", "user.email", "c@x", cwd=other)
    return other


def test_sync_merges_diverged_branch_when_lines_differ(repos, tmp_path):
    ws, origin = repos
    write(ws, "projects/app/.kit.json", '{"goal": "g"}\n')
    write(ws, "projects/app/a.py", "line1\nline2\nline3\n")
    write(ws, "projects/app/b.py", "b\n")
    landing.land(ws, "work")
    landing.sync(ws, "end", open_pr=None)
    other = _caretaker_clone(tmp_path, origin)
    sh("git", "checkout", "-q", "goal/g", cwd=other)
    (other / "projects/app/b.py").write_text("b fixed by caretaker\n")
    sh("git", "commit", "-q", "-am", "Fix b", cwd=other)
    sh("git", "push", "-q", "origin", "goal/g", cwd=other)
    # Meanwhile this computer edited a.py and landed it (a session that ended before the next sync).
    write(ws, "projects/app/a.py", "line1\nline2 edited here\nline3\n")
    landing.land(ws, "local edit")
    report = landing.sync(ws, "start", open_pr=None)
    assert any("brought together" in n for n in report["notes"])
    assert (ws / "projects/app/a.py").read_text() == "line1\nline2 edited here\nline3\n"
    assert (ws / "projects/app/b.py").read_text() == "b fixed by caretaker\n"
    # The branch is still open, so the folder sits in the tree as the branch's version, fully landed.
    assert landing.working_tree_of_prefix(ws, "projects/app") == landing.tree_of_prefix(ws, "goal/g", "projects/app")
    assert len(sh("git", "rev-list", "--parents", "-1", "goal/g", cwd=ws).split()) == 3  # a merge commit


def test_sync_conflict_becomes_needs_you_item(repos, tmp_path):
    ws, origin = repos
    write(ws, "projects/app/.kit.json", '{"goal": "g"}\n')
    write(ws, "projects/app/a.py", "same line\n")
    landing.land(ws, "work")
    landing.sync(ws, "end", open_pr=None)
    other = _caretaker_clone(tmp_path, origin)
    sh("git", "checkout", "-q", "goal/g", cwd=other)
    (other / "projects/app/a.py").write_text("caretaker version\n")
    sh("git", "commit", "-q", "-am", "Fix a", cwd=other)
    sh("git", "push", "-q", "origin", "goal/g", cwd=other)
    write(ws, "projects/app/a.py", "my version\n")
    landing.land(ws, "local edit")
    report = landing.sync(ws, "start", open_pr=None)
    assert report.get("conflicts") == ["app"]
    needs = (ws / "NEEDS-YOU.md").read_text()
    assert "Two versions of app need your pick" in needs and "rebase" not in needs.lower()
    # Nothing was lost: both versions still exist as commits.
    assert sh("git", "show", "goal/g:projects/app/a.py", cwd=ws) == "my version"
    assert sh("git", "show", "origin/goal/g:projects/app/a.py", cwd=ws) == "caretaker version"


def test_sync_after_squash_merge_then_new_edit_starts_from_main(repos, tmp_path):
    """kit pr merge squashes: the merged branch is never main's ancestor."""
    ws, origin = repos
    write(ws, "projects/app/.kit.json", '{"goal": "g"}\n')
    write(ws, "projects/app/a.py", "1\n")
    landing.land(ws, "work")
    landing.sync(ws, "end", open_pr=None)
    other = _caretaker_clone(tmp_path, origin)
    sh("git", "checkout", "-q", "main", cwd=other)
    sh("git", "merge", "-q", "--squash", "origin/goal/g", cwd=other)
    sh("git", "commit", "-q", "-m", "Update app (#1)", cwd=other)
    sh("git", "push", "-q", "origin", "main", ":goal/g", cwd=other)
    # Session two: an unsaved edit sits in the tree before sync (the 2026-11-09 cloud case).
    write(ws, "projects/app/a.py", "2\n")
    report = landing.sync(ws, "start", open_pr=None)
    assert "Update app (#1)" in sh("git", "log", "--format=%s", "-3", cwd=ws)
    assert (ws / "projects/app/a.py").read_text() == "2\n"
    # sync landed the unsaved edit on a fresh branch based on the squash-merged main,
    # so the next pull request has no conflict; a further land finds nothing new.
    assert sh("git", "merge-base", "--is-ancestor", "main", "goal/g", cwd=ws) == ""
    assert sh("git", "log", "--format=%s", "-2", "goal/g", cwd=ws).splitlines() == \
        ["Save unfinished work from an earlier session", "Update app (#1)"]
    again = landing.land(ws, "second edit")
    assert again["landed"] is False or not again["projects"][0]["committed"]


def test_land_from_detached_head_at_main(repos):
    ws, _ = repos
    sh("git", "checkout", "-q", "--detach", cwd=ws)
    write(ws, "docs/cloud.md", "from the cloud\n")
    result = landing.land(ws, "Caretaker: note")
    assert result["landed"]
    assert sh("git", "rev-parse", "--abbrev-ref", "HEAD", cwd=ws) == "main"


def test_land_from_detached_head_ahead_of_stale_main(repos, tmp_path):
    """A cached sandbox checks out the new commit while local main stays behind."""
    ws, origin = repos
    other = _caretaker_clone(tmp_path, origin)
    (other / "docs").mkdir(exist_ok=True)
    (other / "docs" / "n.md").write_text("---\ntype: how-to\n---\nn\n")
    sh("git", "add", "-A", cwd=other); sh("git", "commit", "-q", "-m", "Remote change", cwd=other)
    sh("git", "push", "-q", "origin", "main", cwd=other)
    sh("git", "fetch", "-q", "origin", cwd=ws)
    sh("git", "checkout", "-q", "--detach", "origin/main", cwd=ws)  # local main is now behind HEAD
    write(ws, "docs/cloud.md", "---\ntype: how-to\n---\nfrom the cloud\n")
    result = landing.land(ws, "Caretaker: note")
    assert result["landed"]
    assert sh("git", "rev-parse", "--abbrev-ref", "HEAD", cwd=ws) == "main"
    assert sh("git", "log", "--format=%s", "-2", cwd=ws).splitlines() == ["Caretaker: note", "Remote change"]


def test_land_refuses_off_main(repos):
    ws, _ = repos
    sh("git", "checkout", "-q", "-b", "side", cwd=ws)
    write(ws, "x.md", "x\n")
    with pytest.raises(KitError):
        landing.land(ws, "x")


# ---------------------------------------------------------------- undo (D80)

def _safe_point(ws: Path, origin: Path, date: str) -> str:
    sha = sh("git", "rev-parse", "HEAD", cwd=ws)
    sh("git", "update-ref", f"refs/tags/safe/{date}", sha, cwd=origin)
    return sha


def test_undo_restores_main_as_a_new_commit(repos):
    ws, origin = repos
    good = _safe_point(ws, origin, "2026-11-08")
    write(ws, "docs/note.md", "a mistake\n")
    landing.land(ws, "Oops")
    sh("git", "push", "-q", "origin", "main", cwd=ws)
    bad = sh("git", "rev-parse", "HEAD", cwd=ws)
    listed = undo.list_points(ws)
    assert [p["tag"] for p in listed["points"]] == ["safe/2026-11-08"] and listed["main_is_at"] == []
    result = undo.undo(ws, "safe/2026-11-08")
    assert result["undone"] and result["via"] == "main"
    head = sh("git", "rev-parse", "HEAD", cwd=ws)
    assert sh("git", "rev-parse", "HEAD^{tree}", cwd=ws) == sh("git", "rev-parse", f"{good}^{{tree}}", cwd=ws)
    assert sh("git", "rev-parse", "HEAD^", cwd=ws) == bad  # history kept: the mistake is the parent
    assert sh("git", "rev-parse", "main", cwd=origin) == head  # pushed, fast-forward
    assert not (ws / "docs" / "note.md").exists()
    assert undo.undo(ws, "safe/2026-11-08")["reason"].startswith("main already matches")


def test_undo_keeps_open_project_branches(repos):
    ws, origin = repos
    write(ws, "projects/lister/README.md", "lister\n")
    write(ws, "projects/lister/.kit.json", '{"goal": "sell"}\n')
    landing.land(ws, "Start the lister")  # goes to goal/sell, main untouched
    _safe_point(ws, origin, "2026-11-08")
    write(ws, "README.md", "a mistake\n")
    landing.land(ws, "Oops")
    sh("git", "push", "-q", "origin", "main", cwd=ws)
    write(ws, "projects/lister/README.md", "lister, unsaved edit\n")  # unsaved work in the open branch
    result = undo.undo(ws, "safe/2026-11-08")
    assert result["undone"]
    assert (ws / "README.md").read_text() == "# ws\n"
    # the project folder is the branch's, with the unsaved edit landed on the branch first
    assert (ws / "projects" / "lister" / "README.md").read_text() == "lister, unsaved edit\n"
    assert "unsaved edit" in sh("git", "show", "goal/sell:projects/lister/README.md", cwd=ws)
    assert not sh("git", "ls-tree", "main", "projects/lister", cwd=ws)  # still not on main


def test_undo_refuses_unsaved_work_and_unknown_points(repos):
    ws, origin = repos
    _safe_point(ws, origin, "2026-11-08")
    write(ws, "README.md", "edited\n")
    with pytest.raises(KitError, match="unsaved"):
        undo.undo(ws, "safe/2026-11-08")
    sh("git", "checkout", "-q", "--", "README.md", cwd=ws)
    with pytest.raises(KitError, match="no safe point"):
        undo.undo(ws, "safe/2020-01-01")
    with pytest.raises(KitError, match="which safe point"):
        undo.undo(ws, "yesterday")


def test_undo_goes_through_a_pull_request_when_main_refuses(repos):
    ws, origin = repos
    good = _safe_point(ws, origin, "2026-11-08")
    write(ws, "docs/note.md", "a mistake\n")
    landing.land(ws, "Oops")
    sh("git", "push", "-q", "origin", "main", cwd=ws)
    before = sh("git", "rev-parse", "main", cwd=origin)
    hook = origin / "hooks" / "pre-receive"
    hook.write_text("#!/bin/sh\nwhile read old new ref; do [ \"$ref\" = refs/heads/main ] && { echo 'GH013: rule violations'; exit 1; }; done; exit 0\n")
    hook.chmod(0o755)
    opened = {}

    def fake_open_pr(slug, branch, title, body, base="main", review=None):
        opened.update({"slug": slug, "branch": branch, "title": title})
        return {"number": 9, "sha": sh("git", "rev-parse", branch, cwd=ws), "opened": True}
    import kitlib.github as gh
    statuses = []
    gh_post = gh.post_review_status
    gh.post_review_status = lambda slug, sha, state, desc, target_url="": statuses.append((sha, state, desc)) or {}
    gh.repo_slug = lambda root: "o/r"
    try:
        result = undo.undo(ws, "safe/2026-11-08", open_pr=fake_open_pr)
    finally:
        gh.post_review_status = gh_post
    assert result["via"] == "pull_request" and result["pr"]["number"] == 9
    assert opened["branch"] == "undo/2026-11-08" and statuses and statuses[0][1] == "success"
    assert sh("git", "rev-parse", "main", cwd=origin) == before  # main untouched
    assert sh("git", "rev-parse", "main", cwd=ws) == before  # local main put back
    assert sh("git", "rev-parse", "undo/2026-11-08^{tree}", cwd=origin) == sh("git", "rev-parse", f"{good}^{{tree}}", cwd=ws)
    assert (ws / "docs" / "note.md").exists()  # the working tree is main's again


def test_partition():
    hub, projects = landing.partition(["README.md", "projects/README.md", "projects/app/a.py", "projects/app/sub/b.py",
                                       "projects/other/c.py", "goals/g/README.md"])
    assert hub == ["README.md", "projects/README.md", "goals/g/README.md"]
    assert projects == {"app": ["projects/app/a.py", "projects/app/sub/b.py"], "other": ["projects/other/c.py"]}


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
