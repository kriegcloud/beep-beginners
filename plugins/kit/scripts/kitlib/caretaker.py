"""The caretaker (D44 to D47, D62, D66, D67, D74, D80): what runs with nobody awake.

Three commands (`sweep`, `pr`, `garden`) and three prompt files under
plugins/kit/caretaker/, all runner-neutral. Cloud scheduled tasks are the
default runner; `install --runner actions` emits the claude-code-action form.
`idle` is the cheap REST check every run starts with. The never-list from D46
is spelled out in every prompt verbatim.

How the kit reaches the cloud sandbox (D45, amended 2026-11-09): as the
task's second repository, cloned by the platform. Never a download bootstrap:
the sandbox's auto-mode classifier refuses to run code pulled from the
internet ("Code from External"), and the routine API drops plugin fields.
"""

from __future__ import annotations

import datetime as dt
import json
import uuid
from pathlib import Path

from . import chores, feedback, github, needs_you, okf, packets, retro
from .common import KIT_ROOT, KitError, read_json, today, write_json

KIT_REPO = "kriegcloud/beep-beginners"
PROMPTS = KIT_ROOT / "caretaker"
MODEL = "claude-opus-5-5"
EFFORT = "medium"
STATE = Path(".kit") / "caretaker.json"

NEVER = """Never, with nobody awake: change a price, publish anything, send a message to
anyone, delete data, add a paid service, or keep pushing fixes once a check is
still red after one fix attempt. Each of those becomes a NEEDS-YOU item with a
decision brief instead.

Hard rules, no exceptions, on every plan (D80): never force-push (`--force`,
`--force-with-lease`, a `+` or `:` in front of a branch name); never delete or
move a branch or tag, here or on GitHub (`git branch -D`, `git branch -d main`,
`git tag -d`, `git push --delete`, `gh api -X DELETE`); never `git reset --hard`;
never delete, archive, rename or change the settings, rules or protection of
the repository (`gh repo delete`, `gh api -X PATCH repos/...`, anything under
`rulesets` or `protection`). Only the kit itself trims old `safe/` tags, and
only through `kit caretaker sweep`."""


# ---------------------------------------------------------------- state and budget

def load_state(root: Path) -> dict:
    return read_json(root / STATE, {"schema": "beep-beginners/caretaker/v1", "routines": {}, "fix_attempts": {},
                                    "garden_runs": {}, "plan": None, "runner": "cloud"})


def save_state(root: Path, state: dict) -> None:
    write_json(root / STATE, state)


def fix_allowed(root: Path) -> bool:
    return load_state(root)["fix_attempts"].get(today(), 0) < 1


def fix_used(root: Path) -> dict:
    state = load_state(root)
    state["fix_attempts"][today()] = state["fix_attempts"].get(today(), 0) + 1
    # keep a week of history
    state["fix_attempts"] = {k: v for k, v in state["fix_attempts"].items() if (dt.date.today() - dt.date.fromisoformat(k)).days <= 7}
    save_state(root, state)
    return {"date": today(), "attempts": state["fix_attempts"][today()], "fix_allowed": fix_allowed(root)}


def record_routines(root: Path, ids: dict, runner: str = "cloud", plan: str | None = None) -> dict:
    state = load_state(root)
    state["routines"].update({k: v for k, v in ids.items() if v})
    state["runner"] = runner
    if plan:
        state["plan"] = plan
    save_state(root, state)
    return state


def pause_info(root: Path) -> dict:
    """What the caretaker-pause skill needs: the routine ids to flip."""
    state = load_state(root)
    return {"routines": state["routines"], "runner": state["runner"],
            "note": "Flip each routine's `enabled` with the schedule tool's update action; the kit holds no token for it."}


# ---------------------------------------------------------------- idle check (D74)

def idle(root: Path, garden: bool = False) -> dict:
    """One cheap REST round: is there anything for this run to do?"""
    slug = github.repo_slug(root)
    reasons: list[str] = []
    result: dict = {}
    if not garden:
        try:
            result["safe_point"] = github.safe_tag(slug)  # D80: the daily safe point, idle or not
        except KitError as exc:
            reasons.append(f"could not write today's safe point: {exc}")
    prs = github.list_prs(slug)
    if prs:
        reasons.append(f"{len(prs)} open pull request(s)")
    try:
        alerts = github.dependabot_alerts(slug)
    except KitError as exc:
        alerts = []
        reasons.append(f"could not read Dependabot alerts: {exc}")
    if alerts:
        reasons.append(f"{len(alerts)} Dependabot alert(s)")
    if garden:
        stale = okf.stale_concepts(root)
        if stale:
            reasons.append(f"{len(stale)} stale page(s)")
        if okf.duplicate_drafts(root):
            reasons.append("duplicate drafts")
        if retro.overdue(root):
            reasons.append("overdue retro items")
        if chores.due(root, "cloud"):
            reasons.append("cloud chores due")
    else:
        if chores.due(root, "cloud"):
            reasons.append("cloud chores due")
        if packets.stale(root, "exploration", 30) or packets.stale(root, "goal", 30):
            reasons.append("stale packets")
        if needs_you.is_monday():
            reasons.append("Monday: weekly note")
    return {"idle": not reasons, "reasons": reasons, **result}


# ---------------------------------------------------------------- sweep

def sweep(root: Path, dry_run: bool = False) -> dict:
    slug = github.repo_slug(root)
    report: dict = {"date": today(), "repo": slug, "merged": [], "waiting": [], "needs_fix": [],
                    "retried": [], "alerts": [], "chores": {}, "stale": [], "notes": [],
                    "fix_allowed": fix_allowed(root)}
    for pr in github.list_prs(slug):
        runs = github.check_runs(slug, pr["sha"])
        statuses = github.commit_statuses(slug, pr["sha"])
        gate = github.merge_gate(pr, runs, statuses)
        entry = {**pr, "gate": gate}
        if gate["ok"]:
            if dry_run:
                report["merged"].append({**entry, "dry_run": True})
                continue
            result = github.merge_pr(slug, pr["number"])
            (report["merged"] if result["merged"] else report["waiting"]).append({**entry, "result": result})
        elif gate["pending"]:
            report["waiting"].append(entry)
        elif gate["red"]:
            retry_result = {"retried": False} if dry_run else github.retry_failed_checks(slug, pr["number"])
            if retry_result.get("retried"):
                report["retried"].append({**entry, "retry": retry_result})
            else:
                kit_made = pr["head"].startswith(("goal/", "project/", "claude/", "dependabot/")) or pr["author"] in github.BOT_LOGINS
                report["needs_fix"].append({**entry, "kit_made": kit_made})
        else:
            report["waiting"].append(entry)
    try:
        github.last_alerts_note = None
        report["alerts"] = github.dependabot_alerts(slug)
        if github.last_alerts_note:
            report["alerts_unreadable"] = True
            report["notes"].append(github.last_alerts_note + "; say so in NEEDS-YOU once, not every day")
    except KitError as exc:
        report["alerts"] = []
        report["alerts_unreadable"] = True
        report["notes"].append(f"could not read Dependabot alerts: {exc}")
    if not dry_run:
        try:  # D80: the recovery net, one tag a day, trimmed after 30 days
            report["safe_point"] = {**github.safe_tag(slug), **github.prune_safe_tags(slug)}
        except KitError as exc:
            report["notes"].append(f"could not keep the safe point: {exc}")
    report["chores"] = chores.run_due(root, "cloud", max_seconds=300, limit=None)
    report["stale"] = {"explorations": packets.stale(root, "exploration", 30), "goals": packets.stale(root, "goal", 30)}
    report["needs_you"] = needs_you.load(root)["open"]
    report["monday"] = needs_you.is_monday()
    return report


def handle_pr(root: Path, number: int, max_seconds: int = 1200) -> dict:
    slug = github.repo_slug(root)
    watched = github.watch_pr(slug, number, max_seconds=max_seconds)
    result = {"number": number, "watched": watched, "merged": False, "fix_allowed": fix_allowed(root)}
    gate = watched["gate"]
    if watched["done"] and gate["ok"]:
        merge = github.merge_pr(slug, number)
        result.update({"merged": merge["merged"], "merge": merge})
    elif watched["done"] and gate["red"]:
        result["retry"] = github.retry_failed_checks(slug, number)
        result["action"] = "fix once if this is a kit-made pull request and fix_allowed; otherwise add a NEEDS-YOU item"
    elif watched["done"] and gate.get("review_missing"):
        result["action"] = "kit/review is missing; the next desktop session reviews and posts it"
    else:
        result["action"] = "leave it to the morning sweep"
    return result


# ---------------------------------------------------------------- garden (D62 to D65)

def garden(root: Path, dry_run: bool = False) -> dict:
    state = load_state(root)
    week = dt.date.today().isocalendar()
    key = f"{week[0]}-W{week[1]:02d}"
    report: dict = {"date": today(), "week": key, "already_ran_this_week": key in state["garden_runs"]}
    report["stale"] = okf.stale_concepts(root)
    report["duplicates"] = okf.duplicate_drafts(root)
    report["promoted"] = [] if dry_run else okf.promote_drafts(root)
    report["overdue_retro"] = retro.overdue(root)
    report["nagged"] = [] if dry_run else [n["id"] for n in retro.nag(root)]
    report["chores"] = {} if dry_run else chores.run_due(root, "cloud", max_seconds=600, limit=None)
    report["feedback_pending"] = len([n for n in feedback.load(root)["notes"] if not n["sent"]])
    report["validate"] = okf.validate(root / "docs") if (root / "docs").exists() else {"ok": True}
    if not dry_run:
        okf.write_indexes(root)
        state["garden_runs"][key] = today()
        state["garden_runs"] = dict(list(state["garden_runs"].items())[-8:])
        save_state(root, state)
    return report


# ---------------------------------------------------------------- how the kit reaches the sandbox

def kit_line(route: str, ref: str) -> str:
    """D45 as amended (2026-11-09): only the second-repository route runs in
    the cloud. The routine API drops plugin fields, and the sandbox's
    auto-mode classifier refuses code downloaded from the internet, so there
    is no plugin route and no download bootstrap here (D76)."""
    if route == "actions":
        return ("The kit is checked out at `./.kit-src/plugins/kit` by the workflow; every `kit ...` command below means "
                "`uv run --script ./.kit-src/plugins/kit/scripts/kit.py ...`.")
    if route != "repo":
        raise KitError("the only cloud route is repo (D76)")
    return ("This task has two repositories, cloned side by side under the session's starting folder: the workspace "
            "and `beep-beginners` (the kit, public). First `cd` into the workspace clone. The kit clone starts on its "
            f"default branch, so run `git -C ../beep-beginners fetch -q origin {ref} && git -C ../beep-beginners checkout -q {ref}` "
            "once, then set `KIT=../beep-beginners/plugins/kit/scripts/kit.py`; every `kit ...` command below means "
            "`uv run --script $KIT ...`. Never commit to or push the kit clone.")


def prompt(name: str, workspace_url: str, route: str = "repo", ref: str = "stable") -> str:
    text = (PROMPTS / f"{name}.md").read_text(encoding="utf-8")
    return (text.replace("{{workspace_url}}", workspace_url).replace("{{kit_line}}", kit_line(route, ref))
            .replace("{{never}}", NEVER))


# ---------------------------------------------------------------- routine bodies

def _event(text: str) -> dict:
    return {"data": {"uuid": str(uuid.uuid4()), "session_id": "", "type": "user", "parent_tool_use_id": None,
                     "message": {"content": text, "role": "user"}}}


def install_bodies(workspace_url: str, environment_id: str, cron_utc: str, ref: str = "stable",
                   route: str = "repo", garden_cron_utc: str | None = None, runner: str = "cloud") -> dict:
    """Routine bodies for the cloud runner (two sources: the workspace and the
    kit, D45 as amended) or the Actions runner (D67)."""
    if runner == "actions":
        return actions_workflows(workspace_url, cron_utc, garden_cron_utc or "7 3 * * 1", ref)
    sources = [{"git_repository": {"url": workspace_url}}, {"git_repository": {"url": f"https://github.com/{KIT_REPO}"}}]
    tools = ["Bash", "Read", "Write", "Edit", "Glob", "Grep", "Skill"]

    def body(name: str, text: str, cron: str | None) -> dict:
        b: dict = {"name": name, "enabled": True, "clear_mcp_connections": True,
                   "job_config": {"ccr": {"environment_id": environment_id,
                                          "session_context": {"model": MODEL, "effort": EFFORT, "sources": sources,
                                                              "allowed_tools": tools},
                                          "events": [_event(text)]}}}
        if cron:
            b["cron_expression"] = cron
        return b

    return {
        "sweep": body("beep-beginners caretaker: morning sweep", prompt("sweep", workspace_url, route, ref), cron_utc),
        "pr_opened": body("beep-beginners caretaker: pull request opened", prompt("pr", workspace_url, route, ref), None),
        "garden": body("beep-beginners caretaker: weekly gardener", prompt("garden", workspace_url, route, ref),
                       garden_cron_utc or "7 3 * * 1"),
        # The shape the routines API accepts (2026-11-09): hook_type app, source github,
        # scope_id owner/repo (stored as github.com/owner/repo), an event list, the routine id.
        "webhook": {"hook_type": "app", "source": "github", "scope_id": _slug_from_url(workspace_url),
                    "events": ["pull_request.opened"], "routine_trigger_id": "<id of pr_opened once created>"},
        "notes": ["Create sweep, then pr_opened, then garden with the schedule tool's create action; then "
                  "create_webhook_trigger with this webhook body and pr_opened's id. Record the three ids with "
                  "`kit caretaker record`."],
    }


def actions_workflows(workspace_url: str, cron_utc: str, garden_cron_utc: str, ref: str) -> dict:
    """D67: the same three runs as GitHub Actions workflows on claude-code-action
    with a subscription OAuth token (CLAUDE_CODE_OAUTH_TOKEN repository secret)."""
    def wf(name: str, on: str, text: str) -> str:
        return f"""# {name}: emitted by `kit caretaker install --runner actions` (D67). The token is a
# subscription OAuth token from `claude setup-token`, stored as the repository
# secret CLAUDE_CODE_OAUTH_TOKEN. Rotate it when it expires.
name: caretaker-{name}
on:
{on}
permissions:
  contents: write
  pull-requests: write
  checks: read
  actions: write
jobs:
  run:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          fetch-depth: 0
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          repository: {KIT_REPO}
          ref: {ref}
          path: .kit-src
      - uses: astral-sh/setup-uv@68559e99cc807c1eb7e9238fd43a15bba460eec2 # v10.3.3
      - uses: anthropics/claude-code-action@v1
        with:
          claude_code_oauth_token: ${{{{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}}}
          github_token: ${{{{ secrets.GITHUB_TOKEN }}}}
          prompt: |
{_indent(text, 12)}
          claude_args: "--model {MODEL} --max-turns 80"
"""
    return {
        "sweep": wf("sweep", f"  schedule:\n    - cron: \"{cron_utc}\"\n  workflow_dispatch:", prompt("sweep", workspace_url, "actions", ref)),
        "pr_opened": wf("pr", "  pull_request:\n    types: [opened]", prompt("pr", workspace_url, "actions", ref)),
        "garden": wf("garden", f"  schedule:\n    - cron: \"{garden_cron_utc}\"\n  workflow_dispatch:", prompt("garden", workspace_url, "actions", ref)),
        "notes": ["Write each to .github/workflows/caretaker-<name>.yml, add the CLAUDE_CODE_OAUTH_TOKEN secret, and land."],
    }


def _indent(text: str, n: int) -> str:
    pad = " " * n
    return "\n".join(pad + line if line else "" for line in text.splitlines())


def _slug_from_url(url: str) -> str:
    import re
    m = re.search(r"github\.com[:/]([^/]+)/([^/.\s]+)", url)
    return f"{m.group(1)}/{m.group(2)}" if m else url


def local_time_to_utc_cron(hour: int, minute: int, utc_offset_hours: float, weekday: int | None = None) -> str:
    """7:07 local with offset -6 -> '7 13 * * *'. Daylight time shifts it an hour; fine for a sweep."""
    total = (hour * 60 + minute) - int(utc_offset_hours * 60)
    day_shift = 0
    if total < 0:
        day_shift = -1
    elif total >= 24 * 60:
        day_shift = 1
    total %= 24 * 60
    dow = "*" if weekday is None else str((weekday + day_shift) % 7)
    return f"{total % 60} {total // 60} * * {dow}"
