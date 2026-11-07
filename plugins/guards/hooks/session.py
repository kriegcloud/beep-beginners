# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""SessionStart and SessionEnd upkeep for a workspace repo (decision D25).

  session.py start   banner, changelog refresh, catch-up push, help-request note
  session.py end     save leftover work (operator mode only), push, changelog

Every git call has a timeout and never prompts. Failures are reported, never
raised, so a network hiccup can't wedge a session.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path

GIT_ENV = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "never"}
CHANGELOG = "CHANGELOG-FOR-ED.md"


def git(root: Path, *args: str, timeout: float = 15) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True,
                          timeout=timeout, env=GIT_ENV, check=False)


def repo_root(start: Path) -> Path | None:
    try:
        out = git(start, "rev-parse", "--show-toplevel", timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return Path(out.stdout.strip()) if out.returncode == 0 else None


def has_origin(root: Path) -> bool:
    return git(root, "remote", "get-url", "origin", timeout=5).returncode == 0


def unpushed(root: Path) -> int:
    """Commits on HEAD that origin doesn't have. -1 when unknown."""
    branch = git(root, "rev-parse", "--abbrev-ref", "HEAD", timeout=5).stdout.strip()
    if not branch or branch == "HEAD":
        return -1
    remote = git(root, "rev-parse", "--verify", "--quiet", f"refs/remotes/origin/{branch}", timeout=5)
    if remote.returncode != 0:
        return int(git(root, "rev-list", "--count", "HEAD", timeout=5).stdout.strip() or 0)
    out = git(root, "rev-list", "--count", f"origin/{branch}..HEAD", timeout=5).stdout.strip()
    return int(out or 0)


def push(root: Path) -> str:
    if not has_origin(root):
        return "no GitHub copy is set up yet"
    ahead = unpushed(root)
    if ahead == 0:
        return "already backed up"
    try:
        out = git(root, "push", "--quiet", "origin", "HEAD", timeout=45)
    except subprocess.TimeoutExpired:
        return "backup timed out; it will retry next session"
    if out.returncode != 0:
        return "backup failed: " + (out.stderr.strip().splitlines() or ["unknown error"])[-1]
    return f"backed up {ahead} change(s) to GitHub" if ahead > 0 else "backed up to GitHub"


def save_leftovers(root: Path) -> str | None:
    """Operator mode only: commit anything the agent left uncommitted."""
    if os.environ.get("BEEP_BEGINNERS_MODE", "operator") != "operator":
        return None
    status = git(root, "status", "--porcelain", timeout=10).stdout
    if not status.strip():
        return None
    git(root, "add", "-A", timeout=20)
    out = git(root, "commit", "--quiet", "-m", "Save unfinished work at the end of a session", timeout=20)
    return "saved unfinished work" if out.returncode == 0 else None


def write_changelog(root: Path) -> None:
    """CHANGELOG-FOR-ED.md is derived from commit subjects and gitignored."""
    out = git(root, "log", "-n", "300", "--date=short", "--pretty=format:%ad\t%s", timeout=10)
    if out.returncode != 0:
        return
    days: dict[str, list[str]] = {}
    for line in out.stdout.splitlines():
        date, _, subject = line.partition("\t")
        days.setdefault(date, []).append(subject)
    lines = ["# What changed", "", "Newest first. Claude rewrites this file at the start and end of every session.", ""]
    for date, subjects in days.items():
        lines.append(f"## {dt.date.fromisoformat(date).strftime('%A, %B %d, %Y').replace(' 0', ' ')}")
        lines.append("")
        lines.extend(f"- {s}" for s in subjects)
        lines.append("")
    (root / CHANGELOG).write_text("\n".join(lines), encoding="utf-8")


def start(root: Path) -> dict:
    notes = []
    try:
        result = push(root)
        if "backed up" in result and "already" not in result:
            notes.append(f"Catch-up: {result}.")
        elif "failed" in result or "timed out" in result:
            notes.append(f"Note: {result}.")
        write_changelog(root)
    except (OSError, subprocess.TimeoutExpired) as exc:
        notes.append(f"Note: upkeep skipped ({exc.__class__.__name__}).")
    context = ["Workspace guards are on (git safety, secret files, deletes outside the workspace)."]
    if (root / "HELP-REQUEST.md").exists():
        context.append("HELP-REQUEST.md exists: an earlier problem is waiting for the helper. Mention it once if relevant.")
    context.extend(notes)
    return {
        "systemMessage": "Guards on. " + " ".join(notes) if notes else "Guards on.",
        "hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": " ".join(context)},
    }


def end(root: Path) -> dict:
    parts = []
    try:
        saved = save_leftovers(root)
        if saved:
            parts.append(saved)
        parts.append(push(root))
        write_changelog(root)
    except (OSError, subprocess.TimeoutExpired) as exc:
        parts.append(f"upkeep skipped ({exc.__class__.__name__})")
    return {"systemMessage": "Session end: " + "; ".join(parts) + "."}


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "start"
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        event = {}
    start_dir = Path(os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or os.getcwd())
    root = repo_root(start_dir)
    if root is None:
        print(json.dumps({"systemMessage": "Guards on. (This folder isn't a workspace repo, so backup is off.)"}))
        return 0
    print(json.dumps(start(root) if mode == "start" else end(root)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
