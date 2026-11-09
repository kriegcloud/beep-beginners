"""Hook entry points (D24, D25, D48, D52, D53), called as `kit hook <event>`.

  guard          PreToolUse: git safety, deletes outside the workspace, secret
                 files, and the v3 rules (raw git add/commit, raw merges). Exit 2 blocks.
  session-start  reconcile and pull (kit sync), read NEEDS-YOU.md aloud, run
                 the most overdue chore, refresh WHAT-CHANGED.md, say guards are on.
  session-end    kit land, kit sync --at end, refresh WHAT-CHANGED.md.

Every git call has a timeout and never prompts. Failures are reported in the
hook's message, never raised, so a network hiccup can't wedge a session.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys
from pathlib import Path

from . import chores, landing, needs_you
from .common import KIT_ROOT, KitError, git, repo_root

CHANGELOG = "WHAT-CHANGED.md"
sys.path.insert(0, str(KIT_ROOT / "hooks"))


def _event() -> dict:
    try:
        return json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return {}


def guard(event: dict, start: Path) -> int:
    from rules import check_tool  # noqa: E402  (plugins/kit/hooks/rules.py)
    if not event:
        print("Guard could not read the tool request, so it was blocked to be safe.", file=sys.stderr)
        return 2
    cwd = str(event.get("cwd") or os.getcwd())
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR") or cwd
    reason = check_tool(str(event.get("tool_name", "")), event.get("tool_input") or {}, cwd, project_dir)
    if reason:
        print(f"Blocked by the workspace guard: {reason}", file=sys.stderr)
        return 2
    return 0


def write_changelog(root: Path) -> None:
    out = git(root, "log", "-n", "300", "--date=short", "--pretty=format:%ad\t%s", timeout=20)
    if out.returncode != 0:
        return
    days: dict[str, list[str]] = {}
    for line in out.stdout.splitlines():
        date, _, subject = line.partition("\t")
        days.setdefault(date, []).append(subject)
    lines = ["# What changed", "", "Newest first. Claude rewrites this page at the start and end of every session.", ""]
    for date, subjects in days.items():
        try:
            pretty = dt.date.fromisoformat(date).strftime("%A, %B %d, %Y").replace(" 0", " ")
        except ValueError:
            pretty = date
        lines += [f"## {pretty}", ""] + [f"- {s}" for s in subjects] + [""]
    (root / CHANGELOG).write_text("\n".join(lines), encoding="utf-8")


def _emit(message: str, context: list[str], event_name: str) -> int:
    print(json.dumps({"systemMessage": message,
                      "hookSpecificOutput": {"hookEventName": event_name, "additionalContext": " ".join(context)}}))
    return 0


def session_start(root: Path | None) -> int:
    if root is None:
        print(json.dumps({"systemMessage": "Guards on. (This folder isn't a workspace repo, so backup is off.)"}))
        return 0
    notes: list[str] = []
    context = ["Workspace guards are on: git safety, secret files, deletes outside the workspace, and all",
               "commits go through `kit land` (raw git add/commit and raw merges are blocked)."]
    try:
        report = landing.sync(root, "start", open_pr=None)
        for p in report.get("pushed", []):
            notes.append(f"Backed up {p['branch']}." if p["ok"] else f"Backup of {p['branch']} failed: {p['error']}.")
        notes += [n + "." for n in report.get("notes", []) if "landed on main" in n or "unfinished" in n]
    except (KitError, OSError) as exc:
        notes.append(f"Upkeep skipped ({exc}).")
    try:
        aloud = needs_you.read_aloud(root)
        if aloud["line"]:
            notes.append(aloud["line"])
            context.append("NEEDS-YOU.md has open items; say the line above to the user first, then help them "
                           "through the items when they ask. Resolve one with `kit needs-you resolve <id> --outcome ...`.")
    except (KitError, OSError):
        pass
    try:
        ran = chores.run_due(root, "desktop", max_seconds=120, limit=1)
        notes += ran["lines"]
        if any(r.get("question") for r in ran["ran"]):
            context.append("A chore asked a keep/park/drop question; put it to the user once and act only on a yes.")
    except (KitError, OSError) as exc:
        notes.append(f"Chore skipped ({exc}).")
    try:
        write_changelog(root)
    except OSError:
        pass
    if (root / "HELP-REQUEST.md").exists():
        context.append("HELP-REQUEST.md exists: an earlier problem is waiting for the helper. Mention it once if relevant.")
    message = "Guards on. " + " ".join(notes) if notes else "Guards on."
    return _emit(message, context + notes, "SessionStart")


def session_end(root: Path | None) -> int:
    if root is None:
        print(json.dumps({"systemMessage": "Session end: not a workspace repo, nothing to back up."}))
        return 0
    parts: list[str] = []
    try:
        if os.environ.get("BEEP_BEGINNERS_MODE", "operator") == "operator":
            landed = landing.land(root, "Save unfinished work at the end of a session")
            if landed.get("landed"):
                parts.append("saved unfinished work")
    except KitError as exc:
        parts.append(f"could not save: {exc}")
    try:
        from kit import _open_pr_for_branch  # noqa: E402
        report = landing.sync(root, "end", open_pr=_open_pr_for_branch)
        for p in report.get("pushed", []):
            parts.append(f"backed up {p['branch']}" if p["ok"] else f"backup of {p['branch']} failed: {p['error']}")
        for pr in report.get("prs", []):
            if pr.get("opened"):
                parts.append(f"opened pull request #{pr['number']} for the caretaker")
        parts += [n for n in report.get("notes", []) if "offline" in n or "nothing pushed" in n]
        if not parts:
            parts.append("already backed up")
    except (KitError, OSError) as exc:
        parts.append(f"upkeep skipped ({exc})")
    try:
        write_changelog(root)
    except OSError:
        pass
    print(json.dumps({"systemMessage": "Session end: " + "; ".join(parts) + "."}))
    return 0


def run(event_name: str, start: Path) -> int:
    event = _event()
    if event_name == "guard":
        return guard(event, start)
    start_dir = Path(os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or start)
    root = repo_root(start_dir)
    return session_start(root) if event_name == "session-start" else session_end(root)
