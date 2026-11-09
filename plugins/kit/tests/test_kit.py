# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest>=8"]
# ///
"""Packets, projects, chores, NEEDS-YOU, explain, profile, the merge gate, the
caretaker bodies and the MANIFEST. Run: uv run --script plugins/kit/tests/test_kit.py"""

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
    bodies = caretaker.install_bodies("https://github.com/o/ws", "env_1", "7 13 * * *", route="fetch", ref="main")
    sweep = bodies["sweep"]
    assert sweep["cron_expression"] == "7 13 * * *" and "cron_expression" not in bodies["pr_opened"]
    assert bodies["garden"]["cron_expression"]
    ctx = sweep["job_config"]["ccr"]["session_context"]
    assert ctx["model"] == "claude-opus-5-5" and ctx["sources"] == [{"git_repository": {"url": "https://github.com/o/ws"}}]
    for name in ("sweep", "pr_opened", "garden"):
        text = bodies[name]["job_config"]["ccr"]["events"][0]["data"]["message"]["content"]
        assert caretaker.NEVER in text and "raw.githubusercontent.com/kriegcloud/beep-beginners/main" in text
        assert "{{" not in text and "kit caretaker idle" in text or name == "pr_opened"
    assert sweep["clear_mcp_connections"] is True
    repo = caretaker.install_bodies("https://github.com/o/ws", "env_1", "7 13 * * *")  # the default route
    assert len(repo["sweep"]["job_config"]["ccr"]["session_context"]["sources"]) == 2
    repo_prompt = repo["sweep"]["job_config"]["ccr"]["events"][0]["data"]["message"]["content"]
    assert "checkout -q stable" in repo_prompt and "curl" not in repo_prompt
    plugin = caretaker.install_bodies("https://github.com/o/ws", "env_1", "7 13 * * *", route="plugin", ref="v3")
    assert plugin["sweep"]["enabled_plugins"] == ["kit@beep-beginners"]
    assert plugin["sweep"]["extra_marketplaces"][0]["source"]["ref"] == "v3"
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


# ---------------------------------------------------------------- manifest

def manifest_files() -> list[str]:
    skip = {"tests", "examples", "__pycache__", ".pytest_cache"}
    files = []
    for path in sorted(KIT.rglob("*")):
        rel = path.relative_to(KIT)
        if path.is_dir() or any(part in skip for part in rel.parts) or rel.name == "MANIFEST" or rel.suffix == ".pyc":
            continue
        files.append(rel.as_posix())
    return files


def test_manifest_lists_every_plugin_file():
    expected = manifest_files()
    path = KIT / "MANIFEST"
    if os.environ.get("KIT_WRITE_MANIFEST") == "1":
        path.write_text("# Every file the caretaker fetches from raw.githubusercontent.com (kit caretaker fetch).\n"
                        "# Regenerate: KIT_WRITE_MANIFEST=1 uv run --script plugins/kit/tests/test_kit.py\n"
                        + "\n".join(expected) + "\n")
    listed = [line for line in path.read_text().splitlines() if line and not line.startswith("#")]
    assert listed == expected, "MANIFEST is out of date; regenerate with KIT_WRITE_MANIFEST=1"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
