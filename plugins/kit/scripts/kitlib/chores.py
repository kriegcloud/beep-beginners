"""Chores (D52): a kit-owned list, run one at a time at session start and in
bulk by the caretaker. Each chore has a cadence in days, a place it may run
(desktop, cloud, both) and the one line the user hears.

chores.yaml is read with a small parser for the subset it uses (a top-level
mapping, one list of flat mappings), because hooks must stay standard library.
Timestamps live in .kit/chores.json, committed, so the caretaker and the
desktop share one record.
"""

from __future__ import annotations

import os
import re
import time
from pathlib import Path

from .common import KIT_ROOT, KitError, git, now_iso, plain_days_ago, read_json, write_json
from . import packets

CHORES_FILE = KIT_ROOT / "chores.yaml"
STATE_FILE = Path(".kit") / "chores.json"


# ---------------------------------------------------------------- yaml subset

def _scalar(text: str):
    text = text.strip()
    if text.startswith(("'", '"')) and text.endswith(text[0]) and len(text) >= 2:
        return text[1:-1]
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    if text in ("true", "false"):
        return text == "true"
    return text


def parse_simple_yaml(text: str) -> dict:
    """Parse: `key: value` lines at column 0, and `key:` followed by a list of
    `- key: value` mappings. Comments and blank lines are skipped."""
    result: dict = {}
    current_list: list | None = None
    current_item: dict | None = None
    for raw in text.splitlines():
        line = raw.split(" #", 1)[0].rstrip() if not raw.lstrip().startswith("#") else ""
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        stripped = line.strip()
        if indent == 0:
            key, _, value = stripped.partition(":")
            if value.strip():
                result[key.strip()] = _scalar(value)
                current_list, current_item = None, None
            else:
                current_list = result.setdefault(key.strip(), [])
                current_item = None
        elif stripped.startswith("- ") and current_list is not None:
            current_item = {}
            current_list.append(current_item)
            key, _, value = stripped[2:].partition(":")
            current_item[key.strip()] = _scalar(value)
        elif current_item is not None:
            key, _, value = stripped.partition(":")
            current_item[key.strip()] = _scalar(value)
        else:
            raise KitError(f"chores.yaml: can't read line: {raw!r}")
    return result


def load_chores(path: Path = CHORES_FILE) -> list[dict]:
    data = parse_simple_yaml(path.read_text(encoding="utf-8"))
    chores = data.get("chores", [])
    for c in chores:
        for key in ("id", "cadence", "where", "line"):
            if key not in c:
                raise KitError(f"chores.yaml: chore {c.get('id', '?')} is missing {key}")
    return chores


# ---------------------------------------------------------------- state

def load_state(root: Path) -> dict:
    return read_json(root / STATE_FILE, {"schema": "beep-beginners/chores/v1", "last": {}})


def save_state(root: Path, state: dict) -> None:
    write_json(root / STATE_FILE, state)


def due(root: Path, where: str) -> list[dict]:
    """Chores that may run here, most overdue first."""
    state = load_state(root)
    found = []
    for c in load_chores():
        if c["where"] not in (where, "both"):
            continue
        last = state["last"].get(c["id"], {}).get("at")
        age = plain_days_ago(last) if last else None
        overdue = (age if age is not None else 10_000) - int(c["cadence"])
        if overdue >= 0:
            found.append({**c, "last": last, "overdue_days": overdue})
    found.sort(key=lambda c: (-c["overdue_days"], c["id"]))
    return found


# ---------------------------------------------------------------- handlers

def _chore_index(root: Path, **_) -> dict:
    counts = packets.write_index(root)
    return {"ok": True, "line": "Refreshed the index pages.", **counts}


def _chore_stale(root: Path, kind: str, days: int, **_) -> dict:
    found = packets.stale(root, kind, days)
    noun = "exploration" if kind == "exploration" else "goal"
    if not found:
        return {"ok": True, "line": "", "stale": []}
    names = "; ".join(f"{p['title']} ({p['days']} days)" for p in found)
    verb = "haven't moved" if kind == "exploration" else "have had no progress"
    return {"ok": True, "question": True, "stale": found,
            "line": f"{len(found)} {noun}{'s' if len(found) != 1 else ''} {verb} in a month: {names}. Keep, park or drop?"}


def _chore_links(root: Path, **_) -> dict:
    broken = []
    for folder in ("explorations", "goals", "docs"):
        base = root / folder
        if not base.exists():
            continue
        for md in base.rglob("*.md"):
            text = md.read_text(encoding="utf-8", errors="ignore")
            for m in re.finditer(r"\]\(([^)#?\s]+)(?:#[^)]*)?\)", text):
                target = m.group(1)
                if re.match(r"^[a-z]+:", target):
                    continue
                if not (md.parent / target).exists():
                    broken.append({"file": str(md.relative_to(root)).replace(os.sep, "/"), "link": target})
    line = f"{len(broken)} broken link{'s' if len(broken) != 1 else ''} in your notes need fixing." if broken else ""
    return {"ok": True, "broken": broken, "line": line}


def _chore_backup_age(root: Path, **_) -> dict:
    out = git(root, "log", "-1", "--format=%cI", "origin/main", timeout=20)
    if out.returncode != 0 or not out.stdout.strip():
        return {"ok": True, "line": "Your work hasn't been backed up to GitHub yet.", "days": None, "needs_you": True}
    days = plain_days_ago(out.stdout.strip()) or 0
    line = "Your work was backed up today." if days == 0 else f"Your work was last backed up {days} day{'s' if days != 1 else ''} ago."
    return {"ok": True, "days": days, "line": line, "needs_you": days > 7}


def _chore_onedrive(root: Path, **_) -> dict:
    path = str(root).lower()
    onedrive = os.environ.get("OneDrive", "").lower()
    drift = bool(onedrive and path.startswith(onedrive)) or "onedrive" in path
    return {"ok": True, "drift": drift, "needs_you": drift,
            "line": "Your workspace folder is inside OneDrive, which fights with git. This needs you." if drift else ""}


def _chore_plugin_update(root: Path, **_) -> dict:
    from .common import run
    out = run(["claude", "plugin", "update", "kit@beep-beginners"], timeout=100)
    ok = out.returncode == 0
    return {"ok": ok, "line": "Checked for kit updates." if ok else "Couldn't check for kit updates this time."}


def _chore_dependabot(root: Path, **_) -> dict:
    from . import github
    try:
        slug = github.repo_slug(root)
        prs = [p for p in github.list_prs(slug) if p["author"] in github.BOT_LOGINS]
    except KitError as exc:
        return {"ok": False, "line": "", "error": str(exc)}
    n = len(prs)
    return {"ok": True, "waiting": prs,
            "line": f"{n} update{'s' if n != 1 else ''} {'are' if n != 1 else 'is'} waiting for the caretaker." if n else ""}


def _chore_tools(root: Path, **_) -> dict:
    from .common import run
    script = KIT_ROOT / "scripts" / "tools.py"
    out = run(["uv", "run", "--quiet", "--script", str(script), "verify", "--only-failing"], timeout=110)
    return {"ok": out.returncode == 0, "line": "Checked the apps that had problems last time." if out.returncode == 0 else ""}


HANDLERS = {
    "index": _chore_index,
    "stale-explorations": lambda root, **kw: _chore_stale(root, "exploration", 30),
    "stalled-goals": lambda root, **kw: _chore_stale(root, "goal", 30),
    "broken-links": _chore_links,
    "backup-age": _chore_backup_age,
    "onedrive-drift": _chore_onedrive,
    "plugin-update": _chore_plugin_update,
    "dependabot-waiting": _chore_dependabot,
    "tools-verify": _chore_tools,
}


def run_chore(root: Path, chore: dict) -> dict:
    handler = HANDLERS.get(chore["id"])
    if handler is None:
        return {"id": chore["id"], "ok": False, "line": "", "error": "no handler"}
    started = time.monotonic()
    try:
        result = handler(root)
    except KitError as exc:
        result = {"ok": False, "line": "", "error": str(exc)}
    result.update({"id": chore["id"], "seconds": round(time.monotonic() - started, 1)})
    state = load_state(root)
    state["last"][chore["id"]] = {"at": now_iso(), "ok": result.get("ok", False)}
    save_state(root, state)
    return result


def run_due(root: Path, where: str, max_seconds: int = 120, limit: int | None = 1) -> dict:
    """Run the most overdue chores within a time budget. Desktop sessions pass
    limit=1 (one chore, one line); the caretaker passes limit=None."""
    deadline = time.monotonic() + max_seconds
    results = []
    for chore in due(root, where):
        if limit is not None and len(results) >= limit:
            break
        if time.monotonic() >= deadline:
            break
        results.append(run_chore(root, chore))
    lines = [r["line"] for r in results if r.get("line")]
    return {"where": where, "ran": results, "lines": lines}
