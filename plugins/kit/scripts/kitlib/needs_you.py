"""NEEDS-YOU.md (D53): how the caretaker reaches the user. Three sections:
what needs them, what happened this week, what was done lately. The machine
state is .kit/needs-you.json, committed; the markdown is rendered from it.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from .common import KitError, now_iso, plain_days_ago, read_json, slugify, today, write_json

STATE_FILE = Path(".kit") / "needs-you.json"
DOC = "NEEDS-YOU.md"
KEEP_DONE_DAYS = 30


def load(root: Path) -> dict:
    return read_json(root / STATE_FILE, {"schema": "beep-beginners/needs-you/v1", "open": [], "done": [], "weekly": []})


def save(root: Path, state: dict) -> None:
    write_json(root / STATE_FILE, state)
    render(root, state)


def add(root: Path, title: str, brief: str, source: str = "caretaker", kind: str = "decision") -> dict:
    state = load(root)
    item_id = slugify(title)[:40]
    n, base = 2, item_id
    while any(i["id"] == item_id for i in state["open"]):
        item_id, n = f"{base}-{n}", n + 1
    item = {"id": item_id, "title": title, "brief": brief.strip(), "source": source, "kind": kind,
            "added": today(), "added_at": now_iso()}
    state["open"].append(item)
    save(root, state)
    return item


def resolve(root: Path, item_id: str, outcome: str) -> dict:
    state = load(root)
    for i, item in enumerate(state["open"]):
        if item["id"] == item_id:
            done = {**state["open"].pop(i), "resolved": today(), "outcome": outcome.strip()}
            state["done"].insert(0, done)
            state["done"] = [d for d in state["done"] if (plain_days_ago(d["resolved"]) or 0) <= KEEP_DONE_DAYS]
            save(root, state)
            return done
    raise KitError(f"no open item with id {item_id}")


def weekly(root: Path, text: str) -> dict:
    state = load(root)
    state["weekly"] = [{"week_of": today(), "text": text.strip()}] + state["weekly"][:3]
    save(root, state)
    return state["weekly"][0]


def read_aloud(root: Path) -> dict:
    """The sentence the session-start hook says."""
    state = load(root)
    n = len(state["open"])
    if n == 0:
        return {"count": 0, "line": ""}
    titles = "; ".join(i["title"] for i in state["open"][:3])
    more = f", and {n - 3} more" if n > 3 else ""
    word = {1: "One thing needs", 2: "Two things need", 3: "Three things need"}.get(n, f"{n} things need")
    return {"count": n, "line": f"{word} you: {titles}{more}. Say \"what needs me?\" to go through them.",
            "items": state["open"]}


def render(root: Path, state: dict | None = None) -> str:
    state = state or load(root)
    lines = ["# Needs you", "",
             "The caretaker keeps this page. It lists what it couldn't decide on its own,",
             "what it did this week, and what you've settled lately. Say \"what needs me?\"",
             "in any session to go through the open items.", ""]
    lines += ["## Needs you", ""]
    if state["open"]:
        for item in state["open"]:
            lines += [f"### {item['title']}", "", f"<!-- id: {item['id']} -->",
                      f"Added {item['added']}.", "", item["brief"], ""]
    else:
        lines += ["Nothing right now.", ""]
    lines += ["## This week", ""]
    if state["weekly"]:
        w = state["weekly"][0]
        lines += [f"Week of {w['week_of']}.", "", w["text"], ""]
    else:
        lines += ["No weekly note yet.", ""]
    lines += ["## Done lately", ""]
    if state["done"]:
        lines += [f"- {d['resolved']}: {d['title']}. {d['outcome']}" for d in state["done"]]
        lines.append("")
    else:
        lines += ["Nothing yet.", ""]
    text = "\n".join(lines)
    (root / DOC).write_text(text, encoding="utf-8")
    return text


def is_monday(date: dt.date | None = None) -> bool:
    return (date or dt.date.today()).weekday() == 0
