# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Bookkeeping for explorations and goals. Agents run this; people never need to.

  packet.py new <title> [--notes TEXT]          start explorations/<slug>/
  packet.py set <slug> [--stage S] [--status S] [--next TEXT] [--trail TEXT]
  packet.py graduate <exploration-slug> <goal title> [--mission TEXT]
  packet.py goal-set <slug> [--status S] [--trail TEXT]
  packet.py index                               rewrite both INDEX.md files
  packet.py list                                JSON of every packet, for agents

All paths are relative to --root (default: the current folder). Each packet
keeps its machine state in a hidden .packet.json next to its README.md.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shutil
import sys
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"
STAGES = {
    "notes": "Collecting thoughts. Nothing has been checked yet.",
    "research": "Claude is looking into it and writing up what it finds.",
    "decide": "Working through the open questions with you, one at a time.",
    "plan": "Writing a one-page plan you can agree or disagree with.",
    "graduated": "Done exploring. The work moved into goals.",
}
EXPLORATION_STATUS = ("active", "parked", "dropped", "graduated")
GOAL_STATUS = ("active", "paused", "done", "dropped")


def today() -> str:
    return dt.date.today().isoformat()


def slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug[:60].rstrip("-") or "untitled"


def fill(path: Path, values: dict[str, str]) -> None:
    text = path.read_text(encoding="utf-8")
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value)
    path.write_text(text, encoding="utf-8")


def read_state(folder: Path) -> dict:
    return json.loads((folder / ".packet.json").read_text(encoding="utf-8"))


def write_state(folder: Path, state: dict) -> None:
    state["updated"] = today()
    (folder / ".packet.json").write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def append_trail(folder: Path, text: str) -> None:
    readme = folder / "README.md"
    content = readme.read_text(encoding="utf-8").rstrip("\n")
    readme.write_text(f"{content}\n- {today()}: {text}\n", encoding="utf-8")


def set_readme_section(folder: Path, heading: str, body: str) -> None:
    readme = folder / "README.md"
    text = readme.read_text(encoding="utf-8")
    pattern = re.compile(rf"(## {re.escape(heading)}\n\n)(.*?)(\n\n## )", re.S)
    if pattern.search(text):
        text = pattern.sub(lambda m: m.group(1) + body + m.group(3), text, count=1)
        readme.write_text(text, encoding="utf-8")


def unique_folder(parent: Path, slug: str) -> Path:
    folder, n = parent / slug, 2
    while folder.exists():
        folder, n = parent / f"{slug}-{n}", n + 1
    return folder


def cmd_new(root: Path, args: argparse.Namespace) -> dict:
    parent = root / "explorations"
    parent.mkdir(exist_ok=True)
    folder = unique_folder(parent, slugify(args.title))
    shutil.copytree(TEMPLATES / "exploration", folder)
    values = {"title": args.title, "date": today(), "stage_sentence": STAGES["notes"],
              "first_notes": args.notes or "", "one_paragraph": args.title,
              "next_question": "What made you think of this?"}
    for md in folder.glob("*.md"):
        fill(md, values)
    state = {"kind": "exploration", "slug": folder.name, "title": args.title, "status": "active",
             "stage": "notes", "openQuestions": [], "goals": [], "created": today()}
    write_state(folder, state)
    write_index(root)
    return state


def cmd_set(root: Path, args: argparse.Namespace) -> dict:
    folder = root / "explorations" / args.slug
    state = read_state(folder)
    if args.stage:
        if args.stage not in STAGES:
            sys.exit(f"stage must be one of {', '.join(STAGES)}")
        state["stage"] = args.stage
        set_readme_section(folder, "Where it stands", STAGES[args.stage])
    if args.status:
        if args.status not in EXPLORATION_STATUS:
            sys.exit(f"status must be one of {', '.join(EXPLORATION_STATUS)}")
        state["status"] = args.status
    if args.next is not None:
        state["openQuestions"] = [args.next] if args.next else []
        set_readme_section(folder, "Next question", args.next or "None right now.")
    if args.trail:
        append_trail(folder, args.trail)
    write_state(folder, state)
    write_index(root)
    return state


def cmd_graduate(root: Path, args: argparse.Namespace) -> dict:
    src = root / "explorations" / args.slug
    src_state = read_state(src)
    parent = root / "goals"
    parent.mkdir(exist_ok=True)
    folder = unique_folder(parent, slugify(args.title))
    shutil.copytree(TEMPLATES / "goal", folder)
    values = {"title": args.title, "date": today(), "mission": args.mission or args.title,
              "exploration_title": src_state["title"], "exploration_slug": src.name}
    for md in folder.glob("*.md"):
        fill(md, values)
    state = {"kind": "goal", "slug": folder.name, "title": args.title, "status": "active",
             "exploration": src.name, "created": today()}
    write_state(folder, state)
    src_state["goals"].append(folder.name)
    append_trail(src, f"Became the goal [{args.title}](../../goals/{folder.name}/README.md).")
    write_state(src, src_state)
    write_index(root)
    return state


def cmd_goal_set(root: Path, args: argparse.Namespace) -> dict:
    folder = root / "goals" / args.slug
    state = read_state(folder)
    if args.status:
        if args.status not in GOAL_STATUS:
            sys.exit(f"status must be one of {', '.join(GOAL_STATUS)}")
        state["status"] = args.status
    if args.trail:
        append_trail(folder, args.trail)
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


def write_index(root: Path) -> None:
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("new"); p.add_argument("title"); p.add_argument("--notes")
    p = sub.add_parser("set"); p.add_argument("slug"); p.add_argument("--stage"); p.add_argument("--status")
    p.add_argument("--next"); p.add_argument("--trail")
    p = sub.add_parser("graduate"); p.add_argument("slug"); p.add_argument("title"); p.add_argument("--mission")
    p = sub.add_parser("goal-set"); p.add_argument("slug"); p.add_argument("--status"); p.add_argument("--trail")
    sub.add_parser("index")
    sub.add_parser("list")
    args = parser.parse_args()
    root = args.root.resolve()
    if args.cmd == "index":
        write_index(root)
        result: object = {"ok": True}
    elif args.cmd == "list":
        result = {"explorations": packets(root, "exploration"), "goals": packets(root, "goal")}
    else:
        handler = {"new": cmd_new, "set": cmd_set, "graduate": cmd_graduate, "goal-set": cmd_goal_set}[args.cmd]
        result = handler(root, args)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
