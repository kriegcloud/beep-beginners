# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest>=8"]
# ///
"""Packets, projects, chores, NEEDS-YOU, explain, profile, the merge gate, the
caretaker bodies. Run: uv run --script plugins/kit/tests/test_kit.py"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

KIT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KIT / "scripts"))
from kitlib import caretaker, chores, explain, github, needs_you, packets, profile, project  # noqa: E402
from kitlib.common import KitError  # noqa: E402

ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x", "GIT_COMMITTER_NAME": "t",
       "GIT_COMMITTER_EMAIL": "t@x"}


@pytest.fixture
def ws(tmp_path: Path) -> Path:
    root = tmp_path / "ws"
    shutil.copytree(KIT / "template", root)
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True, env=ENV)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True, env=ENV)
    subprocess.run(["git", "commit", "-q", "-m", "Start"], cwd=root, check=True, env=ENV)
    return root


# ---------------------------------------------------------------- packets

def test_exploration_to_goal(ws):
    e = packets.explore_new(ws, "Start a security company", "my notes")
    assert (ws / "explorations" / e["slug"] / "NOTES.md").read_text().count("my notes") == 1
    packets.explore_set(ws, e["slug"], "research", None, "What does a license cost?", "looked into it")
    index = (ws / "explorations" / "INDEX.md").read_text()
    assert "Start a security company" in index and "What does a license cost?" in index
    g = packets.goal_graduate(ws, e["slug"], "Price the first month", "one sentence")
    assert (ws / "goals" / g["slug"] / "STEPS.md").exists()
    assert "Price the first month" in (ws / "goals" / "INDEX.md").read_text()
    assert packets.read_state(ws / "explorations" / e["slug"])["goals"] == [g["slug"]]
    with pytest.raises(KitError):
        packets.explore_set(ws, e["slug"], "bogus", None, None, None)


def test_stale_packets(ws):
    e = packets.explore_new(ws, "Old idea", None)
    folder = ws / "explorations" / e["slug"]
    state = packets.read_state(folder)
    state["updated"] = "2020-01-01"
    (folder / ".packet.json").write_text(json.dumps(state))
    assert packets.stale(ws, "exploration", 30)[0]["slug"] == e["slug"]
    assert packets.stale(ws, "goal", 30) == []


# ---------------------------------------------------------------- projects

@pytest.mark.parametrize("stack", ["python", "ts"])
def test_project_new(ws, stack):
    packets.explore_new(ws, "An app", None)
    g = packets.goal_graduate(ws, "an-app", "Ship the app", None)
    result = project.new(ws, "my-app", stack, g["slug"], summary="Tracks things.")
    folder = ws / "projects" / "my-app"
    assert (folder / "AGENTS.md").read_text().startswith("# my-app")
    assert "{{" not in (folder / "AGENTS.md").read_text()
    assert not (folder / "WORKFLOW.yml.tmpl").exists()
    wf = (ws / ".github" / "workflows" / "project-my-app.yml").read_text()
    assert 'paths: ["projects/my-app/**"' in wf and "{{" not in wf
    dep = (ws / ".github" / "dependabot.yml").read_text()
    assert 'directory: "/projects/my-app"' in dep and ("uv" if stack == "python" else "bun") in dep
    assert json.loads((folder / ".kit.json").read_text())["goal"] == g["slug"]
    assert result["branch"] == f"goal/{g['slug']}"
    if stack == "python":
        assert (folder / "src" / "my_app" / "__init__.py").exists()
        assert "from my_app import hello" in (folder / "tests" / "test_smoke.py").read_text()
    assert packets.read_state(ws / "goals" / g["slug"])["projects"] == ["my-app"]
    with pytest.raises(KitError):
        project.new(ws, "my-app", stack, None)
    with pytest.raises(KitError):
        project.new(ws, "Bad Name", stack, None)


def test_project_bring_in(ws, tmp_path):
    src = tmp_path / "Documents" / "Scripts"
    src.mkdir(parents=True)
    (src / "lister.py").write_text("x = 1\n")
    (src / "data.xlsx").write_bytes(b"not code")
    result = project.new(ws, "lister", "python", None, source=src)
    assert result["copied"] == ["lister.py"]
    assert (ws / "projects/lister/src/lister.py").exists()
    assert not list((ws / "projects/lister").rglob("*.xlsx"))


# ---------------------------------------------------------------- chores

def test_chores_yaml_parses_and_handlers_exist():
    loaded = chores.load_chores()
    ids = {c["id"] for c in loaded}
    assert ids == set(chores.HANDLERS)
    assert all(c["where"] in ("desktop", "cloud", "both") for c in loaded)
    assert all(isinstance(c["cadence"], int) for c in loaded)


def test_simple_yaml_parser():
    data = chores.parse_simple_yaml('schema: x/v1\n# c\nchores:\n  - id: a\n    cadence: 3\n    line: "L {n}"  # trailing\n  - id: b\n    cadence: 1\n')
    assert data == {"schema": "x/v1", "chores": [{"id": "a", "cadence": 3, "line": "L {n}"}, {"id": "b", "cadence": 1}]}


def test_chores_due_and_run(ws):
    due = chores.due(ws, "desktop")
    assert due and due[0]["overdue_days"] > 1000  # never run: everything is due
    result = chores.run_due(ws, "cloud", max_seconds=60, limit=None)
    ran = {r["id"] for r in result["ran"]}
    assert "index" in ran and "plugin-update" not in ran
    state = json.loads((ws / ".kit" / "chores.json").read_text())
    assert "index" in state["last"]
    assert "index" not in {c["id"] for c in chores.due(ws, "cloud")}


def test_stale_chore_asks_not_moves(ws):
    e = packets.explore_new(ws, "Old idea", None)
    folder = ws / "explorations" / e["slug"]
    state = packets.read_state(folder)
    state["updated"] = "2020-01-01"
    (folder / ".packet.json").write_text(json.dumps(state))
    result = chores.run_chore(ws, {"id": "stale-explorations"})
    assert result["question"] and "Keep, park or drop" in result["line"]
    assert packets.read_state(folder)["status"] == "active"


def test_broken_links_chore(ws):
    (ws / "docs" / "a.md").write_text("see [b](b.md) and [web](https://example.com)\n")
    result = chores.run_chore(ws, {"id": "broken-links"})
    assert result["broken"] == [{"file": "docs/a.md", "link": "b.md"}]


# ---------------------------------------------------------------- needs-you

def test_needs_you_round_trip(ws):
    assert needs_you.read_aloud(ws)["line"] == ""
    item = needs_you.add(ws, "Approve the Mercari fee change", "## Brief\n\nWhat I'm deciding...")
    needs_you.add(ws, "A stale idea", "Keep, park or drop?")
    aloud = needs_you.read_aloud(ws)
    assert aloud["count"] == 2 and aloud["line"].startswith("Two things need you: Approve the Mercari fee change; A stale idea")
    doc = (ws / "NEEDS-YOU.md").read_text()
    assert "### Approve the Mercari fee change" in doc and f"<!-- id: {item['id']} -->" in doc
    done = needs_you.resolve(ws, item["id"], "You said yes.")
    assert done["outcome"] == "You said yes."
    doc = (ws / "NEEDS-YOU.md").read_text()
    assert "Approve the Mercari fee change. You said yes." in doc.split("## Done lately")[1]
    needs_you.weekly(ws, "Quiet week.")
    assert "Quiet week." in (ws / "NEEDS-YOU.md").read_text().split("## This week")[1]
    with pytest.raises(KitError):
        needs_you.resolve(ws, "nope", "x")


# ---------------------------------------------------------------- explain

def test_brief_and_glossary(ws):
    t = explain.brief_template("Pay for 1Password?")
    for heading in ("What I'm deciding", "Your options", "What each costs you", "What I recommend", "What you'd have to do"):
        assert heading in t
    rendered = explain.render_brief({"title": "T", "deciding": "d", "options": ["a", "b"], "costs": ["a: 1", "b: 2"],
                                     "recommendation": "a", "action": "say yes"})
    assert "- a\n- b" in rendered
    with pytest.raises(KitError):
        explain.render_brief({"title": "T"})
    assert explain.glossary_add(ws, "pull request", "a bundle of changes waiting to be checked")["added"]
    assert not explain.glossary_add(ws, "Pull Request", "again")["added"]
    text = (ws / "GLOSSARY.md").read_text()
    assert "- **Pull request**: a bundle of changes waiting to be checked" in text
    assert text.index("**Backup**") < text.index("**Pull request**") < text.index("**Workspace**")


# ---------------------------------------------------------------- profile

EXAMPLE = KIT / "examples" / "profile-card-reseller"


def test_profile_draft_from_example_memories():
    draft = profile.draft((EXAMPLE / "memories.txt").read_text())
    assert draft["sections"]["instructions"] >= 5
    keys = {q["key"]: q["answered_by_memories"] for q in draft["questions"]}
    assert keys["work"] and keys["help_style"] and keys["learn"]
    assert "Who helps you when something breaks on this computer?" in draft["still_to_ask"]


def test_profile_write_matches_example(ws):
    answers = json.loads((EXAMPLE / "answers.json").read_text())
    result = profile.write(ws, answers)
    agents = (ws / "AGENTS.md").read_text()
    assert "<!-- slot:about -->\nThe user is Sam." in agents
    assert "accounting" in agents.split("## How the user learns")[1].split("##")[0]
    assert "The user's helper is Ben." in agents
    for name in answers["skills"]:
        expected = (EXAMPLE / "expected" / ".claude" / "skills" / name["name"] / "SKILL.md").read_text()
        assert (ws / ".claude" / "skills" / name["name"] / "SKILL.md").read_text() == expected
    assert (ws / "card-sales" / "AGENTS.md").exists()
    assert result["profile"] == ".kit/profile.json"
    # No Ed anywhere in the example.
    for path in EXAMPLE.rglob("*"):
        if path.is_file():
            assert not re.search(r"\bEd\b|Lake Forest|Duffers", path.read_text()), path


def test_profile_write_rejects_bad_skill_names(ws):
    with pytest.raises(KitError):
        profile.write(ws, {"name": "A", "about": "b", "skills": [{"name": "Bad Name", "description": "d", "body": "b"}]})


# ---------------------------------------------------------------- merge gate

def pr(**kw):
    base = {"state": "open", "draft": False, "mergeable": True, "mergeable_state": "clean", "author": "sam"}
    return {**base, **kw}


def run(name, status="completed", conclusion="success"):
    return {"name": name, "status": status, "conclusion": conclusion, "url": "", "id": 1}


REVIEWED = [{"context": "kit/review", "state": "success", "description": "reviewed"}]


def test_merge_gate():
    assert github.merge_gate(pr(), [run("gitleaks"), run("tests")], REVIEWED)["ok"]
    assert "no checks" in github.merge_gate(pr(), [], REVIEWED)["reasons"][0]
    g = github.merge_gate(pr(), [run("gitleaks"), run("tests", "in_progress", None)], REVIEWED)
    assert not g["ok"] and g["pending"]
    g = github.merge_gate(pr(), [run("gitleaks"), run("tests", conclusion="failure")], REVIEWED)
    assert not g["ok"] and g["red"] == ["tests"]
    assert not github.merge_gate(pr(), [run("tests")], REVIEWED)["ok"]  # no gitleaks run
    assert not github.merge_gate(pr(), [run("gitleaks", conclusion="failure"), run("tests")], REVIEWED)["ok"]
    assert not github.merge_gate(pr(draft=True), [run("gitleaks")], REVIEWED)["ok"]
    assert not github.merge_gate(pr(mergeable=False, mergeable_state="dirty"), [run("gitleaks")], REVIEWED)["ok"]
    assert github.merge_gate(pr(), [run("gitleaks"), run("semgrep", conclusion="skipped")], REVIEWED)["ok"]


def test_merge_gate_requires_kit_review_except_for_bots():
    g = github.merge_gate(pr(), [run("gitleaks"), run("tests")], [])
    assert not g["ok"] and g["review_missing"] and "kit/review" in g["reasons"][0]
    g = github.merge_gate(pr(), [run("gitleaks")], [{"context": "kit/review", "state": "failure", "description": "2 findings open"}])
    assert not g["ok"] and "kit/review is failure" in g["reasons"][0]
    assert github.merge_gate(pr(author="dependabot[bot]"), [run("gitleaks"), run("tests")], [])["ok"]


def test_actions_run_id():
    assert github.actions_run_id("https://github.com/o/r/actions/runs/123/job/9") == 123
    assert github.actions_run_id("") is None


# ---------------------------------------------------------------- caretaker

def test_install_bodies_shape():
    bodies = caretaker.install_bodies("https://github.com/o/ws", "env_1", "7 13 * * *", ref="v3")
    sweep = bodies["sweep"]
    assert sweep["cron_expression"] == "7 13 * * *" and "cron_expression" not in bodies["pr_opened"]
    assert bodies["garden"]["cron_expression"]
    ctx = sweep["job_config"]["ccr"]["session_context"]
    assert ctx["model"] == "claude-opus-5-5"
    assert ctx["sources"] == [{"git_repository": {"url": "https://github.com/o/ws"}},
                              {"git_repository": {"url": "https://github.com/kriegcloud/beep-beginners"}}]
    for name in ("sweep", "pr_opened", "garden"):
        text = bodies[name]["job_config"]["ccr"]["events"][0]["data"]["message"]["content"]
        assert caretaker.NEVER in text and "checkout -q v3" in text and "{{" not in text
        assert "curl" not in text and "raw.githubusercontent" not in text  # no download bootstrap (D76)
        assert "kit caretaker idle" in text or name == "pr_opened"
    assert sweep["clear_mcp_connections"] is True and "enabled_plugins" not in sweep
    assert bodies["webhook"] == {"hook_type": "app", "source": "github", "scope_id": "o/ws",
                                 "events": ["pull_request.opened"], "routine_trigger_id": "<id of pr_opened once created>"}
    actions = caretaker.install_bodies("https://github.com/o/ws", "", "7 13 * * *", runner="actions")
    assert "anthropics/claude-code-action" in actions["sweep"] and "CLAUDE_CODE_OAUTH_TOKEN" in actions["sweep"]
    assert "pull_request:" in actions["pr_opened"]


def test_local_time_to_utc_cron():
    assert caretaker.local_time_to_utc_cron(7, 7, -6) == "7 13 * * *"
    assert caretaker.local_time_to_utc_cron(23, 30, 2) == "30 21 * * *"
    assert caretaker.local_time_to_utc_cron(21, 7, -6, weekday=0) == "7 3 * * 1"  # Sunday 21:07 Chicago = Monday 03:07 UTC


def test_fix_budget(ws):
    assert caretaker.fix_allowed(ws)
    caretaker.fix_used(ws)
    assert not caretaker.fix_allowed(ws)
    caretaker.record_routines(ws, {"sweep": "trig_1", "pr_opened": "trig_2", "garden": ""}, plan="max5")
    assert caretaker.pause_info(ws)["routines"] == {"sweep": "trig_1", "pr_opened": "trig_2"}


# ---------------------------------------------------------------- the locks (D80)

class FakeGitHub:
    """Records `github.api` calls and answers from a small script."""

    def __init__(self, rulesets="free", tags=()):
        self.calls: list[tuple[str, str, dict | None]] = []
        self.rulesets = rulesets  # "free" -> 403, or a list of existing rulesets
        self.tags = list(tags)
        self.next_id = 100

    def __call__(self, path, method="GET", fields=None, raw=None, **_):
        self.calls.append((method, path, raw))
        if path.startswith("repos/o/r/rulesets"):
            if self.rulesets == "free":
                raise KitError("GitHub GET repos/o/r/rulesets failed: Upgrade to GitHub Pro or make this repository public to enable this feature. (HTTP 403)")
            if method == "GET":
                return self.rulesets
            if method == "POST":
                if any(a.get("actor_type") == "RepositoryRole" for a in raw.get("bypass_actors", [])) and getattr(self, "no_role", False):
                    raise KitError("GitHub POST failed: Validation Failed: bypass_actors RepositoryRole is not valid for this actor")
                self.next_id += 1
                self.rulesets.append({"id": self.next_id, "name": raw["name"], "enforcement": "active"})
                return {"id": self.next_id}
            return {}
        if path == "repos/o/r/git/ref/heads/main":
            return {"object": {"sha": "f" * 40}}
        if path.startswith("repos/o/r/git/matching-refs/tags/safe/"):
            return [{"ref": f"refs/tags/{t}", "object": {"sha": "a" * 40}} for t in self.tags]
        if path == "repos/o/r/git/refs" and method == "POST":
            tag = raw["ref"].removeprefix("refs/tags/")
            if tag in self.tags:
                raise KitError("GitHub POST failed: Reference already exists")
            self.tags.append(tag)
            return {"ref": raw["ref"]}
        if path.startswith("repos/o/r/git/refs/tags/") and method == "DELETE":
            tag = path.removeprefix("repos/o/r/git/refs/tags/")
            if getattr(self, "tags_protected", False):
                raise KitError("GitHub DELETE failed: Cannot delete this tag: Repository rule violations found")
            self.tags.remove(tag)
            return None
        if path == "repos/o/r":
            return {"private": True, "allow_squash_merge": True, "allow_merge_commit": False, "allow_rebase_merge": False,
                    "delete_branch_on_merge": True}
        return {}


def test_enable_security_free_layer_and_pro_hint(ws, monkeypatch):
    fake = FakeGitHub()
    monkeypatch.setattr(github, "api", fake)
    result = github.enable_security("o/r")
    patch = next(raw for m, path, raw in fake.calls if m == "PATCH" and path == "repos/o/r")
    assert patch["allow_merge_commit"] is False and patch["allow_rebase_merge"] is False and patch["allow_squash_merge"] is True
    assert patch["delete_branch_on_merge"] is True
    assert result["squash_only"] == "enabled" and result["protection"]["enforced"] is False
    assert "Free" in result["protection"]["reason"]
    # the one-time Pro line, through kit.py's wrapper
    sys.path.insert(0, str(KIT / "scripts"))
    import kit as kit_cli  # noqa: E402
    first = kit_cli._security_enable(ws, "o/r")
    assert first["pro_hint"]["kind"] == "github-pro" and "$4" in first["pro_hint"]["title"]
    second = kit_cli._security_enable(ws, "o/r")
    assert "pro_hint" not in second
    needs_you.resolve(ws, first["pro_hint"]["id"], "no thanks")
    third = kit_cli._security_enable(ws, "o/r")
    assert "pro_hint" not in third  # asked once, never again
    assert needs_you.read_aloud(ws)["count"] == 0


def test_apply_protection_creates_then_updates(monkeypatch):
    fake = FakeGitHub(rulesets=[])
    monkeypatch.setattr(github, "api", fake)
    first = github.apply_protection("o/r")
    assert first["enforced"] and set(first["rulesets"].values()) == {"created"}
    posted = [raw for m, path, raw in fake.calls if m == "POST" and path == "repos/o/r/rulesets"]
    by_name = {r["name"]: r for r in posted}
    no_erase = by_name[github.RULESET_NO_ERASE]
    assert no_erase["bypass_actors"] == [] and {r["type"] for r in no_erase["rules"]} == {"deletion", "non_fast_forward"}
    assert no_erase["conditions"]["ref_name"]["include"] == ["~DEFAULT_BRANCH"]
    prs = by_name[github.RULESET_PULL_REQUESTS]
    assert {a["actor_type"] for a in prs["bypass_actors"]} == {"RepositoryRole", "Integration"}
    assert any(a["actor_id"] == github.CLAUDE_APP_ID for a in prs["bypass_actors"])
    checks = next(r for r in prs["rules"] if r["type"] == "required_status_checks")
    assert checks["parameters"]["required_status_checks"] == [{"context": "kit/review"}]
    tags = by_name[github.RULESET_TAGS]
    assert tags["target"] == "tag" and tags["conditions"]["ref_name"]["include"] == ["refs/tags/v*", "refs/tags/safe/*"]
    assert {r["type"] for r in tags["rules"]} == {"deletion", "update"}
    # second run updates in place, no duplicates
    second = github.apply_protection("o/r")
    assert set(second["rulesets"].values()) == {"updated"}
    assert len([c for c in fake.calls if c[0] == "PUT" and "/rulesets/" in c[1]]) == 3
    assert len(fake.rulesets) == 3


def test_apply_protection_without_owner_bypass(monkeypatch):
    fake = FakeGitHub(rulesets=[]); fake.no_role = True
    monkeypatch.setattr(github, "api", fake)
    result = github.apply_protection("o/r")
    assert result["enforced"]
    assert result["rulesets"][github.RULESET_NO_ERASE] == "created"
    assert result["rulesets"][github.RULESET_PULL_REQUESTS].startswith("skipped")
    assert result["rulesets"][github.RULESET_TAGS] == "created (no owner bypass)"


def test_safe_points_create_once_and_prune(monkeypatch):
    fake = FakeGitHub(tags=["safe/2026-09-01", "safe/2026-11-01", "safe/not-a-date"])
    monkeypatch.setattr(github, "api", fake)
    made = github.safe_tag("o/r", "2026-11-09")
    assert made == {"tag": "safe/2026-11-09", "sha": "f" * 40, "created": True, "via": "api"}
    again = github.safe_tag("o/r", "2026-11-09")
    assert again["created"] is False
    pruned = github.prune_safe_tags("o/r", today="2026-11-09")
    assert pruned["pruned"] == ["safe/2026-09-01"] and set(pruned["kept"]) == {"safe/2026-11-01", "safe/2026-11-09", "safe/not-a-date"}
    fake.tags_protected = True
    fake.tags.append("safe/2026-01-01")
    protected = github.prune_safe_tags("o/r", today="2026-11-09")
    assert protected["protected"] == ["safe/2026-01-01"] and protected["pruned"] == []
    status = github.protection_status("o/r")
    assert status["squash_only"] and status["rulesets_available"] is False and status["enforced"] is False
    assert [p["tag"] for p in status["safe_points"]][-1] == "safe/not-a-date"


def test_safe_point_falls_back_to_a_push_when_the_proxy_refuses(monkeypatch, tmp_path):
    fake = FakeGitHub()
    real_call = fake.__call__

    def proxy(path, method="GET", fields=None, raw=None, **kw):
        if path == "repos/o/r/git/refs" and method == "POST":
            raise KitError("GitHub POST repos/o/r/git/refs failed: Write access to this GitHub API path is not permitted through this proxy.")
        if path.startswith("repos/o/r/git/refs/tags/") and method == "DELETE":
            raise KitError("GitHub DELETE failed: Write access to this GitHub API path is not permitted through this proxy.")
        return real_call(path, method, fields, raw, **kw)
    monkeypatch.setattr(github, "api", proxy)
    pushes = []

    def fake_git(root, *args, **kw):
        pushes.append(args)
        return subprocess.CompletedProcess(args, 0, "", "")
    monkeypatch.setattr(github, "git", fake_git)
    made = github.safe_tag("o/r", "2026-11-09", root=tmp_path)
    assert made["created"] and made["via"] == "push"
    assert ("push", "-q", "origin", f"{'f' * 40}:refs/tags/safe/2026-11-09") in pushes
    with pytest.raises(KitError):
        github.safe_tag("o/r", "2026-11-10")  # no root: the refusal is reported, not hidden
    fake.tags.append("safe/2026-01-01")
    pruned = github.prune_safe_tags("o/r", today="2026-11-09", root=tmp_path)
    assert pruned["pruned"] == ["safe/2026-01-01"] and ("push", "-q", "origin", "--delete", "refs/tags/safe/2026-01-01") in pushes


def test_merge_pr_posts_review_status_for_bots(monkeypatch):
    calls = []
    pr = {"number": 7, "title": "Bump ruff", "head": {"ref": "dependabot/pip/ruff-1", "sha": "c" * 40}, "base": {"ref": "main"},
          "draft": False, "user": {"login": "dependabot[bot]"}, "html_url": "u", "merged": False, "state": "open",
          "mergeable": True, "mergeable_state": "clean"}

    def fake_api(path, method="GET", fields=None, raw=None, **_):
        calls.append((method, path, raw))
        if path == "repos/o/r/pulls/7":
            return pr
        if "/check-runs" in path:
            return {"check_runs": [{"name": "gitleaks", "status": "completed", "conclusion": "success", "id": 1, "html_url": ""}]}
        if path.endswith("/status"):
            return {"statuses": []}
        if path.endswith("/merge"):
            return {"merged": True, "sha": "d" * 40}
        return {}
    monkeypatch.setattr(github, "api", fake_api)
    result = github.merge_pr("o/r", 7)
    assert result["merged"]
    posted = [raw for m, path, raw in calls if m == "POST" and path == f"repos/o/r/statuses/{'c' * 40}"]
    assert posted and posted[0]["context"] == "kit/review" and posted[0]["state"] == "success"
    assert calls.index(("POST", f"repos/o/r/statuses/{'c' * 40}", posted[0])) < len(calls) - 1  # before the merge


def test_never_list_carries_the_hard_rules():
    for word in ("force-push", "git tag -d", "git push --delete", "gh api -X DELETE", "reset --hard", "rulesets", "gh repo delete"):
        assert word in caretaker.NEVER
    bodies = caretaker.install_bodies("https://github.com/o/ws", "env_1", "7 13 * * *")
    for name in ("sweep", "pr_opened", "garden"):
        assert "Hard rules, no exceptions" in bodies[name]["job_config"]["ccr"]["events"][0]["data"]["message"]["content"]


def test_template_settings_deny_destructive_actions():
    settings = json.loads((KIT / "template" / ".claude" / "settings.json").read_text())
    deny = settings["permissions"]["deny"]
    for pat in ("git tag -d:*", "git push --delete:*", "git branch -d main*", "gh repo delete:*", "gh api -X DELETE:*",
                "gh api * rulesets*", "git update-ref -d:*"):
        assert f"Bash({pat})" in deny and f"PowerShell({pat})" in deny, pat


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
