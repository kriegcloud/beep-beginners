"""The caretaker (D44 to D47): what runs with nobody awake.

`sweep` does the deterministic part of the daily run and returns a plan the
cloud session acts on: merges done, PRs that need a fix, alerts, chores,
staleness questions. `pr` handles one PR-opened fire. `install` renders the
two routine bodies that the onboarding skill hands to the schedule tool.

The never-list from D46 is spelled out in the routine prompts verbatim.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from . import chores, github, landing, needs_you, packets
from .common import KIT_ROOT, KitError, today

KIT_REPO = "kriegcloud/beep-beginners"
RAW_BASE = f"https://raw.githubusercontent.com/{KIT_REPO}"
MODEL = "claude-opus-5-5"
EFFORT = "medium"

NEVER = """Never, with nobody awake: change a price, publish anything, send a message to
anyone, delete data, add a paid service, or keep pushing fixes once a check is
still red after one fix attempt. Each of those becomes a NEEDS-YOU item with a
decision brief instead."""


# ---------------------------------------------------------------- sweep

def sweep(root: Path, dry_run: bool = False) -> dict:
    slug = github.repo_slug(root)
    report: dict = {"date": today(), "repo": slug, "merged": [], "waiting": [], "needs_fix": [],
                    "retried": [], "alerts": [], "chores": {}, "stale": [], "notes": []}
    prs = github.list_prs(slug)
    for pr in prs:
        runs = github.check_runs(slug, pr["sha"])
        gate = github.merge_gate(pr, runs)
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
            retry = {"retried": False} if dry_run else github.retry_failed_checks(slug, pr["number"])
            if retry.get("retried"):
                report["retried"].append({**entry, "retry": retry})
            else:
                kit_made = pr["head"].startswith(("goal/", "project/", "claude/")) or pr["author"] in github.BOT_LOGINS
                report["needs_fix"].append({**entry, "kit_made": kit_made})
        else:
            report["waiting"].append(entry)
    report["alerts"] = github.dependabot_alerts(slug)
    report["chores"] = chores.run_due(root, "cloud", max_seconds=300, limit=None)
    report["stale"] = {"explorations": packets.stale(root, "exploration", 30), "goals": packets.stale(root, "goal", 30)}
    report["needs_you"] = needs_you.load(root)["open"]
    report["monday"] = needs_you.is_monday()
    return report


def handle_pr(root: Path, number: int, max_seconds: int = 1200) -> dict:
    slug = github.repo_slug(root)
    watched = github.watch_pr(slug, number, max_seconds=max_seconds)
    result = {"number": number, "watched": watched, "merged": False}
    if watched["done"] and watched["gate"]["ok"]:
        merge = github.merge_pr(slug, number)
        result.update({"merged": merge["merged"], "merge": merge})
    elif watched["done"] and watched["gate"]["red"]:
        result["retry"] = github.retry_failed_checks(slug, number)
        result["action"] = "fix once if this is a kit-made pull request; otherwise add a NEEDS-YOU item"
    else:
        result["action"] = "leave it to the morning sweep"
    return result


# ---------------------------------------------------------------- bootstrap in the sandbox

def fetch_manifest_text() -> str:
    return (KIT_ROOT / "MANIFEST").read_text(encoding="utf-8")


def bootstrap_snippet(ref: str = "main") -> str:
    """The shell lines a routine prompt starts with when the plugin route is
    unavailable (D45): one file from raw.githubusercontent.com, then the rest."""
    return (f"mkdir -p ~/kit && curl -fsSL {RAW_BASE}/{ref}/plugins/kit/scripts/kit.py -o ~/kit/kit.py "
            f"&& uv run --script ~/kit/kit.py caretaker fetch --ref {ref} --into ~/kit/plugins/kit "
            f"&& export KIT=~/kit/plugins/kit/scripts/kit.py")


# ---------------------------------------------------------------- routine bodies

def _event(prompt: str) -> dict:
    return {"data": {"uuid": str(uuid.uuid4()), "session_id": "", "type": "user", "parent_tool_use_id": None,
                     "message": {"content": prompt, "role": "user"}}}


def sweep_prompt(workspace_url: str, ref: str = "main", kit_route: str = "fetch") -> str:
    kit_line = {
        "plugin": "The kit plugin is enabled on this routine; run its script through the plugin root.",
        "fetch": "First get the kit:\n\n```\n" + bootstrap_snippet(ref) + "\n```\n\nThen use `uv run --script $KIT ...` for every kit command below.",
        "repo": f"The kit is cloned next to the workspace as `beep-beginners`; set `KIT=../beep-beginners/plugins/kit/scripts/kit.py` and use `uv run --script $KIT ...`.",
    }[kit_route]
    return f"""You are the caretaker for the workspace at {workspace_url}. Work inside its clone. The person who owns it never reads GitHub; everything they need to know goes into NEEDS-YOU.md in plain words.

{kit_line}

Do the morning sweep:

1. Run `kit caretaker sweep` and read its JSON. It has already merged every pull request whose checks were all green (through `kit pr merge`, the only merge path) and re-run failed checks once where that hadn't been tried.
2. For each entry under `needs_fix` that is `kit_made` (a `goal/`, `project/` or Dependabot branch): check out that branch in a worktree, read the failing check's log with `gh api` (REST only; `gh pr` and GraphQL don't work here), make one fix attempt for a lint or test failure, commit and push the branch, and run `kit pr watch <number>` then `kit pr merge <number>`. If it is still red after that one attempt, stop and add a NEEDS-YOU item.
3. For each entry under `needs_fix` that is not kit-made, and for anything that would change a price, publish, send, delete data or add a paid service: do not act. Add a NEEDS-YOU item with a decision brief (`kit explain --template brief` gives the shape: what I'm deciding, the options in one line each, what each costs in time, money or risk, what I recommend and why, what they'd have to do).
4. Read `alerts` (Dependabot). A fix that is just a version bump with green checks merges itself through the PR path. Anything else becomes a NEEDS-YOU item.
5. Read `stale`: every exploration or goal untouched for 30 days becomes one NEEDS-YOU question, keep, park or drop. Never move or delete anything yourself.
6. If `monday` is true, write the weekly note with `kit needs-you weekly --text "..."`: three or four sentences on what happened this week, in the owner's words, no jargon.
7. Finish with `kit land --message "Caretaker: <what changed, one line>"` and `kit sync --at end`. Push only `main` and existing kit branches; never force-push, never delete branches, never create a pull request on the kit repository.

Write everything the owner will read as if to a smart friend who doesn't code: short sentences, no file paths, no git words. Add a glossary entry (`kit glossary add`) the first time a term appears.

{NEVER}

If the kit cannot be fetched or a command keeps failing, write what happened to NEEDS-YOU.md through `kit needs-you add` if that works, and stop. Do not improvise around the kit."""


def pr_prompt(workspace_url: str, ref: str = "main", kit_route: str = "fetch") -> str:
    kit_line = {
        "plugin": "The kit plugin is enabled on this routine; run its script through the plugin root.",
        "fetch": "First get the kit:\n\n```\n" + bootstrap_snippet(ref) + "\n```\n\nThen use `uv run --script $KIT ...` for every kit command below.",
        "repo": "The kit is cloned next to the workspace as `beep-beginners`; set `KIT=../beep-beginners/plugins/kit/scripts/kit.py`.",
    }[kit_route]
    return f"""You are the caretaker for the workspace at {workspace_url}. A pull request was just opened there; its number is in the routine-fire-payload block, or find it with `gh api repos/<owner>/<repo>/pulls?state=open` (REST only; `gh pr` and GraphQL don't work here).

{kit_line}

1. Run `kit caretaker pr <number> --max-seconds 1200`. It waits for the checks, merges when every check is green (the only merge path), and re-runs failed checks once.
2. If it reports red checks on a kit-made branch (`goal/`, `project/`, Dependabot): make one fix attempt for a lint or test failure in a worktree of that branch, push, and run `kit pr merge <number>` again. Still red: stop and add a NEEDS-YOU item with a decision brief (`kit explain --template brief`).
3. If the checks are still running when the time runs out, do nothing more; the morning sweep picks it up.
4. Finish with `kit land --message "Caretaker: <one line>"` and `kit sync --at end` if you changed anything on main.

{NEVER}

Write anything the owner reads in plain words: short sentences, no file paths, no git words."""


def install_bodies(workspace_url: str, environment_id: str, cron_utc: str, ref: str = "main",
                   route: str = "fetch", sources_extra: list[str] | None = None) -> dict:
    sources = [{"git_repository": {"url": workspace_url}}]
    if route == "repo":
        sources.append({"git_repository": {"url": f"https://github.com/{KIT_REPO}"}})
    for extra in sources_extra or []:
        sources.append({"git_repository": {"url": extra}})
    tools = ["Bash", "Read", "Write", "Edit", "Glob", "Grep", "Skill"]

    def body(name: str, prompt: str, cron: str | None) -> dict:
        b: dict = {"name": name, "enabled": True, "clear_mcp_connections": True,
                   "job_config": {"ccr": {"environment_id": environment_id,
                                          "session_context": {"model": MODEL, "effort": EFFORT, "sources": sources,
                                                              "allowed_tools": tools},
                                          "events": [_event(prompt)]}}}
        if cron:
            b["cron_expression"] = cron
        if route == "plugin":
            b["extra_marketplaces"] = [{"name": "beep-beginners", "source": {"source": "github", "repo": KIT_REPO}}]
            b["enabled_plugins"] = ["kit@beep-beginners"]
        return b

    return {
        "sweep": body("beep-beginners caretaker: morning sweep", sweep_prompt(workspace_url, ref, route), cron_utc),
        "pr_opened": body("beep-beginners caretaker: pull request opened", pr_prompt(workspace_url, ref, route), None),
        "webhook": {"source": "github", "repository": workspace_url, "events": ["pull_request.opened"],
                    "routine_trigger_id": "<id of pr_opened once created>"},
        "notes": ["Create the sweep with the schedule tool's create action, then pr_opened, then create_webhook_trigger "
                  "with pr_opened's id. Record both ids in the onboarding state and the evidence."],
    }


def local_time_to_utc_cron(hour: int, minute: int, utc_offset_hours: float) -> str:
    """7:07 local with offset -6 -> '7 13 * * *'. Daylight time shifts it an hour; fine for a sweep."""
    total = (hour * 60 + minute) - int(utc_offset_hours * 60)
    total %= 24 * 60
    return f"{total % 60} {total // 60} * * *"
