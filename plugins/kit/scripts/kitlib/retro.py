"""Retros get actioned (D65). Items live in the goal packet's .retro.json and
render to RETRO.md; every item has a kind, a due date and a home.

  chore     a recurring fix -> a chores.yaml override (kept in .kit/chores-overrides.json)
  step      a one-off        -> a step in the goal packet (STEPS.md)
  decision  needs the user   -> a NEEDS-YOU brief
  lesson    worth keeping    -> a docs/lessons concept with the retro as source
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from . import needs_you, okf
from .common import KitError, plain_days_ago, read_json, slugify, today, write_json

KINDS = ("chore", "step", "decision", "lesson")


def _file(root: Path, goal: str) -> Path:
    folder = root / "goals" / goal
    if not folder.exists():
        raise KitError(f"no goal at goals/{goal}")
    return folder / ".retro.json"


def load(root: Path, goal: str) -> dict:
    return read_json(_file(root, goal), {"schema": "beep-beginners/retro/v1", "goal": goal, "items": [], "retros": []})


def save(root: Path, goal: str, state: dict) -> None:
    write_json(_file(root, goal), state)
    render(root, goal, state)


def open_retro(root: Path, goal: str, summary: str) -> dict:
    state = load(root, goal)
    scorecard = scorecard_for(state)
    state["retros"].insert(0, {"date": today(), "summary": summary.strip(), "scorecard": scorecard})
    save(root, goal, state)
    return {"goal": goal, "date": today(), "scorecard": scorecard}


def add(root: Path, goal: str, text: str, kind: str, due: str, source: str = "") -> dict:
    if kind not in KINDS:
        raise KitError(f"kind must be one of {', '.join(KINDS)}")
    try:
        dt.date.fromisoformat(due)
    except ValueError:
        raise KitError("due must be a date like 2026-12-01") from None
    state = load(root, goal)
    item_id = f"{slugify(text)[:30]}-{len(state['items']) + 1}"
    item = {"id": item_id, "text": text.strip(), "kind": kind, "due": due, "added": today(), "done": None,
            "nagged": False, "source": source or f"goals/{goal}/RETRO.md"}
    if kind == "lesson":
        concept = okf.concept_new(root, "lessons", text.strip()[:80], "lesson", text.strip(),
                                  description=text.strip()[:140],
                                  sources=[{"id": "retro", "resource": item["source"], "title": f"Retro for {goal}"}],
                                  status="draft")
        item["home"] = concept["path"]
    elif kind == "decision":
        brief = (f"**What I'm deciding.** {text.strip()}\n\n**Your options.**\n- Do it\n- Leave it\n\n"
                 f"**What each costs you.**\n- Decide by {due}.\n\n**What I recommend, and why.** "
                 f"Decide by the date so the work doesn't stall.\n\n**What you'd have to do.** Say yes or no.")
        needs = needs_you.add(root, text.strip()[:80], brief, source=f"retro:{goal}", kind="retro")
        item["home"] = f"NEEDS-YOU.md#{needs['id']}"
    elif kind == "chore":
        path = root / ".kit" / "chores-overrides.json"
        overrides = read_json(path, {"schema": "beep-beginners/chores-overrides/v1", "proposed": []})
        overrides["proposed"].append({"id": item_id, "text": text.strip(), "goal": goal, "added": today()})
        write_json(path, overrides)
        item["home"] = ".kit/chores-overrides.json (proposed; a NEEDS-YOU brief adopts it)"
    else:
        steps = root / "goals" / goal / "STEPS.md"
        if steps.exists():
            steps.write_text(steps.read_text(encoding="utf-8").rstrip("\n") + f"\n- [ ] {text.strip()} (from the retro, due {due})\n",
                             encoding="utf-8")
        item["home"] = f"goals/{goal}/STEPS.md"
    state["items"].append(item)
    save(root, goal, state)
    return item


def done(root: Path, goal: str, item_id: str, note: str = "") -> dict:
    state = load(root, goal)
    for item in state["items"]:
        if item["id"] == item_id:
            item["done"] = today()
            item["note"] = note
            save(root, goal, state)
            return item
    raise KitError(f"no retro item {item_id} in {goal}")


def overdue(root: Path) -> list[dict]:
    found = []
    goals = root / "goals"
    for state_file in sorted(goals.glob("*/.retro.json")) if goals.exists() else []:
        state = read_json(state_file, {})
        for item in state.get("items", []):
            if item.get("done"):
                continue
            days = plain_days_ago(item["due"])
            if days is not None and days > 0:
                found.append({**item, "goal": state.get("goal", state_file.parent.name), "days_overdue": days})
    return found


def nag(root: Path) -> list[dict]:
    """One NEEDS-YOU item per overdue retro item that hasn't been nagged yet."""
    nagged = []
    for item in overdue(root):
        if item.get("nagged"):
            continue
        brief = (f"**What I'm deciding.** The retro for {item['goal']} asked for: {item['text']}. It was due {item['due']} "
                 f"and hasn't happened.\n\n**Your options.**\n- Do it now (I can, if it's mine to do)\n- Drop it\n- Pick a new date\n\n"
                 f"**What each costs you.**\n- Doing it: the time it takes\n- Dropping it: the lesson may repeat\n\n"
                 f"**What I recommend, and why.** Pick a new date if it still matters.\n\n**What you'd have to do.** Say which.")
        needs_you.add(root, f"Overdue from the {item['goal']} retro: {item['text'][:50]}", brief,
                      source=f"retro:{item['goal']}", kind="retro-nag")
        state = load(root, item["goal"])
        for it in state["items"]:
            if it["id"] == item["id"]:
                it["nagged"] = True
        save(root, item["goal"], state)
        nagged.append(item)
    return nagged


def scorecard_for(state: dict) -> dict:
    items = state.get("items", [])
    return {"total": len(items), "done": sum(1 for i in items if i.get("done")),
            "overdue": sum(1 for i in items if not i.get("done") and (plain_days_ago(i["due"]) or 0) > 0)}


def render(root: Path, goal: str, state: dict) -> str:
    lines = ["---", "type: retro", f"title: Retro for {goal}", f'description: "What we learned working on {goal}, and what each lesson turned into."',
             "status: stable", "---", "", f"# Retro: {goal}", "",
             "Every item has a home and a date. The gardener checks the dates and asks once about anything overdue.", ""]
    for r in state.get("retros", []):
        sc = r.get("scorecard") or {}
        lines += [f"## {r['date']}", "", r["summary"], "",
                  f"Scorecard from the previous retro: {sc.get('done', 0)} of {sc.get('total', 0)} items done, {sc.get('overdue', 0)} overdue.", ""]
    lines += ["## Items", ""]
    for item in state.get("items", []):
        mark = "x" if item.get("done") else " "
        lines.append(f"- [{mark}] {item['text']} ({item['kind']}, due {item['due']}, lives in {item['home']})")
    lines.append("")
    text = "\n".join(lines)
    (root / "goals" / goal / "RETRO.md").write_text(text, encoding="utf-8")
    return text


def list_items(root: Path, goal: str | None = None) -> list[dict]:
    if goal:
        return load(root, goal)["items"]
    found = []
    goals = root / "goals"
    for state_file in sorted(goals.glob("*/.retro.json")) if goals.exists() else []:
        found += json.loads(state_file.read_text(encoding="utf-8")).get("items", [])
    return found
