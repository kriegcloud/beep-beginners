# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest>=8"]
# ///
"""docs/ as an OKF bundle, trust and staleness, retros, feedback, migrations
(D60 to D65, D72, D73). Run: uv run --script plugins/kit/tests/test_okf.py"""

from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

KIT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KIT / "scripts"))
from kitlib import feedback, migrate, needs_you, okf, packets, retro  # noqa: E402
from kitlib.common import KitError  # noqa: E402

ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@x"}


@pytest.fixture
def ws(tmp_path: Path) -> Path:
    root = tmp_path / "ws"
    shutil.copytree(KIT / "template", root)
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True, env=ENV)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True, env=ENV)
    subprocess.run(["git", "commit", "-q", "-m", "Start"], cwd=root, check=True, env=ENV)
    return root


# ---------------------------------------------------------------- yaml subset

def test_yaml_round_trip():
    meta = {"type": "business-fact", "title": "Fees: 10%", "description": "A sentence, with a comma.",
            "sources": [{"id": "s1", "resource": "https://example.com/a", "title": "Fee page"}],
            "generated": {"by": "process:kit", "at": "2026-11-08T00:00:00Z"},
            "verified": [{"by": "human:sam", "at": "2026-11-09T00:00:00Z"}], "status": "stable", "tags": ["a", "b"]}
    text = okf.join_frontmatter(meta, "body\n")
    parsed, body = okf.split_frontmatter(text)
    assert parsed == meta and body == "body\n"


def test_yaml_flow_and_bare_mapping():
    meta = okf.parse_yaml('type: lesson\nverified: {by: human:ed, at: "2026-01-01T00:00:00Z"}\ntags: [x, "y z"]\n')
    assert meta["verified"] == {"by": "human:ed", "at": "2026-01-01T00:00:00Z"} and meta["tags"] == ["x", "y z"]
    assert okf.trust_tier(meta) == "human-reviewed"


# ---------------------------------------------------------------- template bundle

def test_template_docs_is_conformant():
    result = okf.validate(KIT / "template" / "docs")
    assert result["ok"], result["errors"]
    assert result["concepts"] == 3


def test_concept_lifecycle(ws):
    made = okf.concept_new(ws, "", "Mercari fee is ten percent", "business-fact", "Mercari takes 10%.[^s1]\n\n[^s1]: Mercari fee page",
                           description="What Mercari charges per sale.",
                           sources=[{"id": "s1", "resource": "https://example.com/fees"}], export=True)
    path = ws / made["path"]
    meta, _ = okf.read(path)
    assert meta["type"] == "business-fact" and meta["status"] == "draft" and meta["generated"]["by"] == "process:kit"
    assert made["stale_after"] and okf.trust_tier(meta) == "unverified"
    # 30-day default for money facts
    when = dt.datetime.fromisoformat(made["stale_after"].replace("Z", "+00:00"))
    assert 29 <= (when - dt.datetime.now(dt.timezone.utc)).days <= 30
    assert okf.validate(ws / "docs")["ok"]
    index = (ws / "docs" / "index.md").read_text()
    assert "Mercari fee is ten percent" in index and "[unverified, draft]" in index
    log = (ws / "docs" / "log.md").read_text()
    assert f"## {dt.date.today().isoformat()}" in log and "**Creation**" in log
    # verification by a person promotes the draft and sets the tier
    okf.verify(ws, made["id"].split("/", 1)[1], "human:sam")  # a bare id works too
    meta, _ = okf.read(path)
    assert meta["status"] == "stable" and okf.trust_tier(meta) == "human-reviewed"
    okf.set_status(ws, made["id"], "deprecated", "superseded")
    meta, _ = okf.read(path)
    assert meta["status"] == "deprecated" and "stale_after" not in meta
    with pytest.raises(KitError):
        okf.concept_new(ws, "", "Health note", "health", "x", export=True)


def test_stale_and_promote(ws):
    made = okf.concept_new(ws, "", "Old how-to", "how-to", "steps", status="draft")
    path = ws / made["path"]
    meta, body = okf.read(path)
    meta["stale_after"] = "2020-01-01T00:00:00Z"
    meta["generated"]["at"] = "2020-01-01T00:00:00Z"
    okf.write(path, meta, body)
    stale = okf.stale_concepts(ws)
    assert [s["path"] for s in stale] == [made["path"]]
    assert okf.promote_drafts(ws) == [made["path"]]
    assert okf.read(path)[0]["status"] == "stable"
    # packets count too: an active exploration carries stale_after
    e = packets.explore_new(ws, "An idea", None)
    meta, _ = okf.read(ws / "explorations" / e["slug"] / "README.md")
    assert meta["type"] == "exploration" and meta["lifecycle"] == "active" and meta["stale_after"]
    assert packets.read_state(ws / "explorations" / e["slug"])["status"] == "active"  # lifecycle stays in .packet.json
    packets.confirm(ws / "explorations" / e["slug"], "human:sam")
    assert okf.trust_tier(okf.read(ws / "explorations" / e["slug"] / "README.md")[0]) == "human-reviewed"


def test_duplicate_drafts(ws):
    okf.concept_new(ws, "", "Mercari fee is ten percent", "business-fact", "a")
    okf.concept_new(ws, "", "The Mercari fee: ten percent of the sale", "business-fact", "b")
    okf.concept_new(ws, "", "Shipping slabs in bubble mailers", "workflow", "c")
    groups = okf.duplicate_drafts(ws)
    assert len(groups) == 1 and len(groups[0]) == 2


# ---------------------------------------------------------------- retro (D65)

def test_retro_items_find_their_homes(ws):
    packets.explore_new(ws, "An app", None)
    g = packets.goal_graduate(ws, "an-app", "Ship it", None)
    retro.open_retro(ws, g["slug"], "Went fine, two lessons.")
    lesson = retro.add(ws, g["slug"], "Always check the date on a job posting", "lesson", "2026-12-31")
    assert lesson["home"].startswith("docs/lessons/") and (ws / lesson["home"]).exists()
    assert okf.read(ws / lesson["home"])[0]["sources"][0]["resource"].endswith("RETRO.md")
    step = retro.add(ws, g["slug"], "Rename the import script", "step", "2026-12-31")
    assert "Rename the import script" in (ws / "goals" / g["slug"] / "STEPS.md").read_text()
    decision = retro.add(ws, g["slug"], "Pay for the pro tier?", "decision", "2026-12-31")
    assert decision["home"].startswith("NEEDS-YOU.md#") and needs_you.read_aloud(ws)["count"] == 1
    chore = retro.add(ws, g["slug"], "Check the tracker every Monday", "chore", "2020-01-01")
    assert "chores-overrides" in chore["home"]
    overdue = retro.overdue(ws)
    assert [i["id"] for i in overdue] == [chore["id"]]
    nagged = retro.nag(ws)
    assert len(nagged) == 1 and retro.nag(ws) == []  # nags once
    assert needs_you.read_aloud(ws)["count"] == 2
    text = (ws / "goals" / g["slug"] / "RETRO.md").read_text()
    assert text.startswith("---\ntype: retro") and "Check the tracker every Monday" in text
    retro.done(ws, g["slug"], step["id"], "done")
    second = retro.open_retro(ws, g["slug"], "Round two.")
    assert second["scorecard"] == {"total": 4, "done": 1, "overdue": 1}
    assert okf.validate(ws / "docs")["ok"]


# ---------------------------------------------------------------- feedback (D73)

def test_feedback_is_scrubbed_and_asks_once(ws):
    note = feedback.add(ws, "The chore line names C:\\Users\\sam\\Workspace and sam@example.com",
                        "Say 'your workspace folder' instead. See https://github.com/x/y", file="plugins/kit/chores.yaml")
    assert "<path>" in note["what"] and "<email>" in note["what"] and "<url>" in note["fix"]
    assert "sam@" not in (ws / "KIT-FEEDBACK.md").read_text()
    feedback.add(ws, "Second note", "Second fix")
    items = needs_you.load(ws)["open"]
    assert len([i for i in items if i["kind"] == "kit-feedback"]) == 1


# ---------------------------------------------------------------- migrations (D72)

def test_migrate_runs_once(ws):
    (ws / "CHANGELOG-FOR-ED.md").write_text("old\n")
    glossary = ws / "GLOSSARY.md"
    glossary.write_text("# Glossary\n\n- **A**: b\n")
    settings = ws / ".claude" / "settings.json"
    data = json.loads(settings.read_text())
    data["permissions"]["deny"] = [r for r in data["permissions"]["deny"] if "tag -d" not in r and "DELETE" not in r]
    settings.write_text(json.dumps(data))
    first = migrate.run(ws)
    assert [r["migration"] for r in first["ran"]] == ["0001-v3-baseline", "0002-v3.1-locks"]
    assert all(r["applied"] for r in first["ran"])
    assert not (ws / "CHANGELOG-FOR-ED.md").exists() and glossary.read_text().startswith("---")
    # D80: the v3.1 migration adds the missing deny rules and the two glossary terms
    deny = json.loads(settings.read_text())["permissions"]["deny"]
    assert "Bash(git tag -d:*)" in deny and "PowerShell(gh api -X DELETE:*)" in deny
    assert "**Safe point**" in glossary.read_text() and "**Lock**" in glossary.read_text()
    second = migrate.run(ws)
    assert second["ran"] == [] and second["applied_total"] == 2
    state = json.loads((ws / ".kit" / "migrations.json").read_text())
    assert "0001-v3-baseline" in state["applied"] and "0002-v3.1-locks" in state["applied"]


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
