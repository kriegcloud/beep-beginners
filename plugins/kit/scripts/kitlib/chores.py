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
    found.sort(key=lambda c: (c["id"] != "migrate", -c["overdue_days"], c["id"]))
    return found


# ---------------------------------------------------------------- handlers

def _chore_index(root: Path, **_) -> dict:
    from . import okf
    counts = packets.write_index(root)
    counts.update(okf.write_indexes(root))
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


def _chore_migrate(root: Path, **_) -> dict:
    from . import migrate
    result = migrate.run(root)
    n = len(result["ran"])
    return {"ok": True, "ran": result["ran"], "line": f"Applied {n} kit update{'s' if n != 1 else ''} to your workspace." if n else ""}


def _chore_caretaker_setup(root: Path, **_) -> dict:
    from . import caretaker
    state = caretaker.load_state(root)
    if state.get("routines"):
        return {"ok": True, "line": "", "done": True}
    plan = state.get("plan") or read_json(root / ".kit" / "profile.json", {}).get("plan")
    if plan and not str(plan).lower().startswith("max"):
        return {"ok": True, "line": "", "skipped": "Pro plan: the caretaker needs Max (D66); session-start chores cover upkeep"}
    return {"ok": True, "question": True, "agent_action": "caretaker-setup skill",
            "line": "Ten minutes to set up your caretaker? It runs on your Claude account while you're away and tidies up."}


def _chore_merge_green(root: Path, **_) -> dict:
    """D66: a desktop session merges green pull requests so Pro users get the
    same result a day later; harmless alongside the caretaker."""
    from . import github
    try:
        slug = github.repo_slug(root)
        merged = []
        for pr in github.list_prs(slug):
            gate = github.merge_gate(pr, github.check_runs(slug, pr["sha"]), github.commit_statuses(slug, pr["sha"]))
            if gate["ok"]:
                result = github.merge_pr(slug, pr["number"])
                if result["merged"]:
                    merged.append(pr["number"])
    except KitError as exc:
        return {"ok": False, "line": "", "error": str(exc)}
    n = len(merged)
    return {"ok": True, "merged": merged, "line": f"{n} piece{'s' if n != 1 else ''} of finished work passed the checks and went into the main copy." if n else ""}


def _chore_caretaker_health(root: Path, **_) -> dict:
    from . import caretaker
    state = caretaker.load_state(root)
    if not state.get("routines"):
        return {"ok": True, "line": ""}
    return {"ok": True, "agent_action": "schedule list_runs",
            "line": "Check the caretaker's last run with the schedule tool; if it was rejected at the usage limit, add one NEEDS-YOU line."}


def _chore_locks(root: Path, **_) -> dict:
    """D80, monthly from the owner's own machine: re-apply the free layer,
    apply the enforced layer if the plan now allows it (a Pro upgrade shows
    up here within a month), and trim safe points the caretaker couldn't."""
    from . import github
    try:
        slug = github.repo_slug(root)
        enabled = github.enable_security(slug)
        pruned = github.prune_safe_tags(slug)
    except KitError as exc:
        return {"ok": False, "line": "", "error": str(exc)}
    enforced = enabled.get("protection", {}).get("enforced")
    line = ("Checked the locks on your GitHub backup: GitHub itself now refuses to erase the main copy."
            if enforced else "Checked the locks on your GitHub backup and trimmed old safe points.")
    return {"ok": True, "security": enabled, "safe_points": pruned, "line": line}


def _chore_okf_validate(root: Path, **_) -> dict:
    """`kit docs validate` (offline, always) plus okflint (D82) when uv can run
    it. A skipped lint is a note for the agent, never a line for the user."""
    from . import okf
    docs = root / "docs"
    if not docs.exists():
        return {"ok": True, "line": ""}
    result = okf.validate(docs)
    linted = okf.lint(docs, timeout=120)
    files = {e.split(" ", 2)[1].rstrip(":") for e in result["errors"]}
    files |= {e.split(" ", 2)[1].rstrip(":") for e in linted["errors"]}
    if not files:
        return {"ok": True, "line": "", "validate": result, "lint": linted}
    n = len(files)
    return {"ok": False, "validate": result, "lint": linted,
            "line": f"{n} page{'s' if n != 1 else ''} in docs need fixing (see the validate and lint output)."}


def _chore_docs_promote(root: Path, **_) -> dict:
    from . import okf
    promoted = okf.promote_drafts(root)
    n = len(promoted)
    return {"ok": True, "promoted": promoted, "line": f"{n} note{'s' if n != 1 else ''} from earlier sessions {'are' if n != 1 else 'is'} now settled." if n else ""}


HANDLERS = {
    "migrate": _chore_migrate,
    "caretaker-setup": _chore_caretaker_setup,
    "merge-green": _chore_merge_green,
    "caretaker-health": _chore_caretaker_health,
    "locks": _chore_locks,
    "okf-validate": _chore_okf_validate,
    "docs-promote": _chore_docs_promote,
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
