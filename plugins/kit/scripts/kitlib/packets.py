"""Explorations and goals: the packet bookkeeping that used to be packet.py.

Each packet keeps its machine state in a hidden .packet.json next to its
README.md. People read every other file; agents run these commands.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from .common import TEMPLATES, KitError, fill, slugify, today
from . import okf

STAGES = {
    "notes": "Collecting thoughts. Nothing has been checked yet.",
    "research": "Claude is looking into it and writing up what it finds.",
    "decide": "Working through the open questions with you, one at a time.",
    "plan": "Writing a one-page plan you can agree or disagree with.",
    "graduated": "Done exploring. The work moved into goals.",
}
EXPLORATION_STATUS = ("active", "parked", "dropped", "graduated")
GOAL_STATUS = ("active", "paused", "done", "dropped")


def read_state(folder: Path) -> dict:
    path = folder / ".packet.json"
    if not path.exists():
        raise KitError(f"{folder.name} has no .packet.json; is the slug right?")
    return json.loads(path.read_text(encoding="utf-8"))


def write_state(folder: Path, state: dict) -> None:
    state["updated"] = today()
    (folder / ".packet.json").write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    mirror_frontmatter(folder, state)


def mirror_frontmatter(folder: Path, state: dict) -> None:
    """D60: the README carries OKF trust fields so one staleness query covers
    the hub. `.packet.json` stays the lifecycle of record; the frontmatter
    mirrors it. OKF `status` is the trust tier, not the packet's lifecycle."""
    readme = folder / "README.md"
    if not readme.exists():
        return
    meta, body = okf.read(readme)
    meta = meta or {}
    lifecycle = state.get("status", "active")
    meta.update({"type": state.get("kind", "exploration"), "title": state.get("title", folder.name),
                 "description": f"{state.get('kind', 'exploration').capitalize()}: {state.get('title', folder.name)} ({lifecycle}).",
                 "lifecycle": lifecycle})
    meta.setdefault("generated", {"by": okf.KIT_ACTOR, "at": f"{state.get('created', today())}T00:00:00Z"})
    meta["status"] = "deprecated" if lifecycle == "dropped" else "stable"
    if lifecycle in ("active", "paused"):
        meta["stale_after"] = f"{_plus_days(state.get('updated') or today(), 30)}T00:00:00Z"
    else:
        meta.pop("stale_after", None)
    okf.write(readme, meta, body)


def _plus_days(date_text: str, days: int) -> str:
    import datetime as _dt
    return (_dt.date.fromisoformat(date_text[:10]) + _dt.timedelta(days=days)).isoformat()


def confirm(folder: Path, by: str) -> dict:
    """The user confirmed this packet still matters: record human verification."""
    state = read_state(folder)
    readme = folder / "README.md"
    meta, body = okf.read(readme)
    meta = meta or {}
    existing = meta.get("verified") or []
    if isinstance(existing, dict):
        existing = [existing]
    meta["verified"] = existing + [{"by": by, "at": okf.now_iso().replace("+00:00", "Z")}]
    okf.write(readme, meta, body)
    write_state(folder, state)
    return {"slug": folder.name, "verified_by": by}


def append_trail(folder: Path, text: str) -> None:
    readme = folder / "README.md"
    content = readme.read_text(encoding="utf-8").rstrip("\n")
    readme.write_text(f"{content}\n- {today()}: {text}\n", encoding="utf-8")


def set_readme_section(folder: Path, heading: str, body: str) -> None:
    readme = folder / "README.md"
    text = readme.read_text(encoding="utf-8")
    pattern = re.compile(rf"(## {re.escape(heading)}\n\n)(.*?)(\n\n## )", re.S)
    if pattern.search(text):
        readme.write_text(pattern.sub(lambda m: m.group(1) + body + m.group(3), text, count=1), encoding="utf-8")


def unique_folder(parent: Path, slug: str) -> Path:
    folder, n = parent / slug, 2
    while folder.exists():
        folder, n = parent / f"{slug}-{n}", n + 1
    return folder


def _fill_folder(folder: Path, values: dict[str, str]) -> None:
    for md in folder.glob("*.md"):
        md.write_text(fill(md.read_text(encoding="utf-8"), values), encoding="utf-8")


def explore_new(root: Path, title: str, notes: str | None) -> dict:
    parent = root / "explorations"
    parent.mkdir(exist_ok=True)
    folder = unique_folder(parent, slugify(title))
    shutil.copytree(TEMPLATES / "exploration", folder)
    _fill_folder(folder, {"title": title, "date": today(), "stage_sentence": STAGES["notes"],
                          "first_notes": notes or "", "one_paragraph": title,
                          "next_question": "What made you think of this?"})
    state = {"kind": "exploration", "slug": folder.name, "title": title, "status": "active",
             "stage": "notes", "openQuestions": [], "goals": [], "created": today()}
    write_state(folder, state)
    write_index(root)
    return state


def explore_set(root: Path, slug: str, stage: str | None, status: str | None,
                next_question: str | None, trail: str | None) -> dict:
    folder = root / "explorations" / slug
    state = read_state(folder)
    if stage:
        if stage not in STAGES:
            raise KitError(f"stage must be one of {', '.join(STAGES)}")
        state["stage"] = stage
        set_readme_section(folder, "Where it stands", STAGES[stage])
    if status:
        if status not in EXPLORATION_STATUS:
            raise KitError(f"status must be one of {', '.join(EXPLORATION_STATUS)}")
        state["status"] = status
    if next_question is not None:
        state["openQuestions"] = [next_question] if next_question else []
        set_readme_section(folder, "Next question", next_question or "None right now.")
    if trail:
        append_trail(folder, trail)
    write_state(folder, state)
    write_index(root)
    return state


def goal_graduate(root: Path, slug: str, title: str, mission: str | None) -> dict:
    src = root / "explorations" / slug
    src_state = read_state(src)
    parent = root / "goals"
    parent.mkdir(exist_ok=True)
    folder = unique_folder(parent, slugify(title))
    shutil.copytree(TEMPLATES / "goal", folder)
    _fill_folder(folder, {"title": title, "slug": folder.name, "date": today(), "mission": mission or title,
                          "exploration_title": src_state["title"], "exploration_slug": src.name})
    state = {"kind": "goal", "slug": folder.name, "title": title, "status": "active",
             "exploration": src.name, "created": today(), "projects": []}
    write_state(folder, state)
    src_state.setdefault("goals", []).append(folder.name)
    append_trail(src, f"Became the goal [{title}](../../goals/{folder.name}/README.md).")
    write_state(src, src_state)
    write_index(root)
    return state


def goal_set(root: Path, slug: str, status: str | None, trail: str | None) -> dict:
    folder = root / "goals" / slug
    state = read_state(folder)
    if status:
        if status not in GOAL_STATUS:
            raise KitError(f"status must be one of {', '.join(GOAL_STATUS)}")
        state["status"] = status
    if trail:
        append_trail(folder, trail)
    write_state(folder, state)
    write_index(root)
    return state


def packets(root: Path, kind: str) -> list[dict]:
    base = root / ("explorations" if kind == "exploration" else "goals")
    found = []
    for state_file in sorted(base.glob("*/.packet.json")) if base.exists() else []:
        try:
            found.append(json.loads(state_file.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            continue
    return found


def list_all(root: Path) -> dict:
    return {"explorations": packets(root, "exploration"), "goals": packets(root, "goal")}


def write_index(root: Path) -> dict:
    explorations = packets(root, "exploration")
    goals = packets(root, "goal")
    lines = ["# Explorations", "", "Ideas being thought through. Say \"I want to explore ...\" to start one.", ""]
    for status, label in (("active", "Being worked on"), ("parked", "On hold"),
                          ("graduated", "Turned into goals"), ("dropped", "Decided against")):
        group = [p for p in explorations if p["status"] == status]
        if not group:
            continue
        lines += [f"## {label}", ""]
        for p in group:
            question = f" Next: {p['openQuestions'][0]}" if p.get("openQuestions") and status == "active" else ""
            lines.append(f"- [{p['title']}]({p['slug']}/README.md), updated {p['updated']}.{question}")
        lines.append("")
    if not explorations:
        lines += ["Nothing yet.", ""]
    if (root / "explorations").exists():
        (root / "explorations" / "INDEX.md").write_text("\n".join(lines), encoding="utf-8")

    lines = ["# Goals", "", "Work that came out of an exploration and is ready to do.", ""]
    for status, label in (("active", "In progress"), ("paused", "Paused"), ("done", "Done"), ("dropped", "Dropped")):
        group = [p for p in goals if p["status"] == status]
        if not group:
            continue
        lines += [f"## {label}", ""]
        lines += [f"- [{p['title']}]({p['slug']}/README.md), updated {p['updated']}." for p in group]
        lines.append("")
    if not goals:
        lines += ["Nothing yet.", ""]
    if (root / "goals").exists():
        (root / "goals" / "INDEX.md").write_text("\n".join(lines), encoding="utf-8")
    return {"explorations": len(explorations), "goals": len(goals)}


def stale(root: Path, kind: str, days: int) -> list[dict]:
    """Packets untouched for `days` days that still look active."""
    from .common import plain_days_ago
    active = "active"
    found = []
    for p in packets(root, kind):
        if p.get("status") != active:
            continue
        age = plain_days_ago(p.get("updated") or p.get("created") or "")
        if age is not None and age >= days:
            found.append({"slug": p["slug"], "title": p["title"], "days": age})
    return found
