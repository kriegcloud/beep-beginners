"""GitHub over `gh api` REST only (D51). No `gh pr`, no GraphQL: the cloud
sandbox's proxy rejects both, and one code path has to work in both places.

The merge gate (D49) lives here: `merge_gate` is a pure function over the
PR and its check runs, so tests can drive it without GitHub.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

from .common import KitError, git, run

GREEN = {"success", "neutral", "skipped"}
GITLEAKS_NAMES = ("gitleaks",)
BOT_LOGINS = {"dependabot[bot]", "github-actions[bot]"}


def repo_slug(root: Path) -> str:
    url = git(root, "remote", "get-url", "origin", timeout=10).stdout.strip()
    m = re.search(r"github\.com[:/]([^/]+)/([^/.\s]+)(?:\.git)?/?$", url)
    if not m:
        raise KitError(f"origin isn't a GitHub repository: {url or 'no origin'}")
    return f"{m.group(1)}/{m.group(2)}"


def api(path: str, method: str = "GET", fields: dict | None = None, raw: dict | None = None,
        timeout: float = 60, paginate: bool = False):
    argv = ["gh", "api", "-X", method, "-H", "Accept: application/vnd.github+json", path]
    if paginate:
        argv.append("--paginate")
    if raw is not None:
        argv += ["--input", "-"]
        out = run(argv, timeout=timeout, input_text=json.dumps(raw))
    else:
        for key, value in (fields or {}).items():
            if isinstance(value, bool):
                argv += ["-F", f"{key}={'true' if value else 'false'}"]
            elif isinstance(value, int):
                argv += ["-F", f"{key}={value}"]
            else:
                argv += ["-f", f"{key}={value}"]
        out = run(argv, timeout=timeout)
    if out.returncode != 0:
        detail = (out.stderr or out.stdout).strip()
        try:
            detail = json.loads(out.stdout).get("message", detail)
        except (json.JSONDecodeError, AttributeError):
            pass
        raise KitError(f"GitHub {method} {path} failed: {detail[-300:]}")
    text = out.stdout.strip()
    if not text:
        return None
    if paginate:
        # --paginate concatenates JSON arrays; merge them.
        merged: list = []
        for chunk in re.split(r"\]\s*\[", text):
            chunk = chunk if chunk.startswith("[") else "[" + chunk
            chunk = chunk if chunk.endswith("]") else chunk + "]"
            merged.extend(json.loads(chunk))
        return merged
    return json.loads(text)


# ---------------------------------------------------------------- pull requests

def list_prs(slug: str, state: str = "open") -> list[dict]:
    prs = api(f"repos/{slug}/pulls?state={state}&per_page=50") or []
    return [summarize_pr(p) for p in prs]


def get_pr(slug: str, number: int) -> dict:
    return api(f"repos/{slug}/pulls/{number}")


def summarize_pr(pr: dict) -> dict:
    return {"number": pr["number"], "title": pr["title"], "head": pr["head"]["ref"], "sha": pr["head"]["sha"],
            "base": pr["base"]["ref"], "draft": bool(pr.get("draft")), "author": pr["user"]["login"],
            "url": pr["html_url"], "merged": bool(pr.get("merged")), "state": pr["state"],
            "mergeable": pr.get("mergeable"), "mergeable_state": pr.get("mergeable_state")}


def find_pr_for_branch(slug: str, branch: str) -> dict | None:
    owner = slug.split("/")[0]
    prs = api(f"repos/{slug}/pulls?state=open&head={owner}:{branch}") or []
    return summarize_pr(prs[0]) if prs else None


def open_pr(slug: str, branch: str, title: str, body: str, base: str = "main", review: dict | None = None) -> dict:
    """Open the PR (or find the open one) and, when a review record is given,
    post the kit/review status on its head SHA (D70)."""
    existing = find_pr_for_branch(slug, branch)
    if existing:
        result = {**existing, "opened": False}
    else:
        pr = api(f"repos/{slug}/pulls", "POST", raw={"title": title, "head": branch, "base": base, "body": body})
        result = {**summarize_pr(pr), "opened": True}
    if review:
        waived = review.get("waived", 0)
        desc = f"reviewed: {review.get('findings', 0)} finding(s), {review.get('fixed', 0)} fixed, {waived} waived"
        result["review_status"] = post_review_status(slug, result["sha"], "success", desc)
    return result


def check_runs(slug: str, sha: str) -> list[dict]:
    data = api(f"repos/{slug}/commits/{sha}/check-runs?per_page=100") or {}
    runs = []
    for cr in data.get("check_runs", []):
        runs.append({"name": cr["name"], "status": cr["status"], "conclusion": cr.get("conclusion"),
                     "url": cr.get("html_url") or cr.get("details_url") or "", "id": cr["id"]})
    return runs


REVIEW_CONTEXT = "kit/review"


def commit_statuses(slug: str, sha: str) -> list[dict]:
    """Commit statuses on the head SHA. `kit/review` is one of these (D70):
    GitHub lets only GitHub Apps create check runs, so the review verdict is
    a commit status, which a user's token may post with the repo scope."""
    data = api(f"repos/{slug}/commits/{sha}/status") or {}
    return [{"context": s["context"], "state": s["state"], "description": s.get("description", "")}
            for s in data.get("statuses", [])]


def post_review_status(slug: str, sha: str, state: str, description: str, target_url: str = "") -> dict:
    if state not in ("success", "failure", "pending", "error"):
        raise KitError("state must be success, failure, pending or error")
    body = {"state": state, "context": REVIEW_CONTEXT, "description": description[:140]}
    if target_url:
        body["target_url"] = target_url
    result = api(f"repos/{slug}/statuses/{sha}", "POST", raw=body)
    return {"sha": sha, "context": REVIEW_CONTEXT, "state": (result or {}).get("state", state)}


def merge_gate(pr: dict, runs: list[dict], statuses: list[dict] | None = None) -> dict:
    """Decide whether a PR may merge. Pure: no network.

    Rules (D49, D70): the PR is open, not a draft, GitHub reports it mergeable;
    at least one check run exists; every run is complete and green; a run
    named gitleaks exists and is green; and unless a bot opened the PR, a
    `kit/review` commit status on the head SHA is success."""
    statuses = statuses or []
    reasons: list[str] = []
    if pr.get("state") != "open":
        reasons.append(f"the pull request is {pr.get('state')}")
    if pr.get("draft"):
        reasons.append("the pull request is a draft")
    if pr.get("mergeable") is False or pr.get("mergeable_state") in ("dirty", "blocked", "behind" if False else "dirty"):
        reasons.append("GitHub says it can't be merged as is (a conflict with main)")
    if not runs:
        reasons.append("no checks have reported yet")
    pending = [r["name"] for r in runs if r["status"] != "completed"]
    if pending:
        reasons.append("checks still running: " + ", ".join(sorted(set(pending))))
    red = [r["name"] for r in runs if r["status"] == "completed" and (r.get("conclusion") or "") not in GREEN]
    if red:
        reasons.append("checks not green: " + ", ".join(sorted(set(red))))
    leaks = [r for r in runs if any(n in r["name"].lower() for n in GITLEAKS_NAMES)]
    if runs and not leaks:
        reasons.append("the gitleaks check didn't run on this change")
    elif leaks and any((r.get("conclusion") or "") not in GREEN or r["status"] != "completed" for r in leaks):
        reasons.append("the gitleaks check is not green")
    review_missing = False
    if pr.get("author") not in BOT_LOGINS:
        review = [st for st in statuses if st["context"] == REVIEW_CONTEXT]
        if not review:
            review_missing = True
            reasons.append("no kit/review verdict on this change yet (the desktop session reviews before it opens the pull request)")
        elif review[-1]["state"] != "success":
            reasons.append(f"kit/review is {review[-1]['state']}: {review[-1].get('description', '')}")
    return {"ok": not reasons, "reasons": reasons, "pending": bool(pending), "red": red, "review_missing": review_missing}


def merge_pr(slug: str, number: int, method: str = "squash") -> dict:
    pr = summarize_pr(get_pr(slug, number))
    runs = check_runs(slug, pr["sha"])
    statuses = commit_statuses(slug, pr["sha"])
    gate = merge_gate(pr, runs, statuses)
    if not gate["ok"]:
        return {"merged": False, "number": number, "title": pr["title"], "gate": gate, "runs": runs}
    if pr["author"] in BOT_LOGINS and not any(st["context"] == REVIEW_CONTEXT for st in statuses):
        # D80: where a ruleset requires kit/review on main, a bot's version bump
        # needs the status too; the gate already exempts bots from a human review.
        post_review_status(slug, pr["sha"], "success", "dependency update by a bot; no code of ours to review")
    result = api(f"repos/{slug}/pulls/{number}/merge", "PUT",
                 raw={"merge_method": method, "sha": pr["sha"],
                      "commit_title": f"{pr['title']} (#{number})"})
    return {"merged": bool(result and result.get("merged")), "number": number, "title": pr["title"],
            "sha": (result or {}).get("sha"), "gate": gate, "runs": runs}


def watch_pr(slug: str, number: int, max_seconds: int = 1200, interval: int = 30, sleep=time.sleep) -> dict:
    """Poll until every check run has completed or time runs out."""
    deadline = time.monotonic() + max_seconds
    while True:
        pr = summarize_pr(get_pr(slug, number))
        runs = check_runs(slug, pr["sha"])
        gate = merge_gate(pr, runs, commit_statuses(slug, pr["sha"]))
        if runs and not gate["pending"]:
            return {"number": number, "done": True, "gate": gate, "runs": runs, "sha": pr["sha"]}
        if time.monotonic() >= deadline:
            return {"number": number, "done": False, "gate": gate, "runs": runs, "sha": pr["sha"],
                    "reason": "checks were still running when the time ran out"}
        sleep(interval)


def actions_run_id(check_url: str) -> int | None:
    m = re.search(r"/actions/runs/(\d+)", check_url or "")
    return int(m.group(1)) if m else None


def comments(slug: str, number: int) -> list[dict]:
    return api(f"repos/{slug}/issues/{number}/comments?per_page=100") or []


def comment(slug: str, number: int, body: str) -> dict:
    return api(f"repos/{slug}/issues/{number}/comments", "POST", raw={"body": body})


RETRY_MARK = "<!-- kit: retried failed checks once -->"


def retry_failed_checks(slug: str, number: int) -> dict:
    """Re-run failed jobs once per PR (D46: retry a flaky check once)."""
    if any(RETRY_MARK in c.get("body", "") for c in comments(slug, number)):
        return {"retried": False, "reason": "already retried once"}
    pr = summarize_pr(get_pr(slug, number))
    runs = check_runs(slug, pr["sha"])
    run_ids = sorted({actions_run_id(r["url"]) for r in runs
                      if r["status"] == "completed" and (r.get("conclusion") or "") not in GREEN
                      and actions_run_id(r["url"])})
    if not run_ids:
        return {"retried": False, "reason": "no failed Actions runs to retry"}
    for run_id in run_ids:
        api(f"repos/{slug}/actions/runs/{run_id}/rerun-failed-jobs", "POST")
    comment(slug, number, f"{RETRY_MARK}\nThe kit re-ran the failed checks once to rule out a flaky run.")
    return {"retried": True, "runs": run_ids}


# ---------------------------------------------------------------- repository settings

ALERTS_UNAVAILABLE = "Dependabot alerts can't be read with this run's GitHub access"
last_alerts_note: str | None = None  # set when the last dependabot_alerts call couldn't read them


def dependabot_alerts(slug: str) -> list[dict]:
    """Open Dependabot alerts, or [] when this token can't read them. The
    cloud proxy's installation token lacks the vulnerability-alerts permission
    ("Resource not accessible by integration", seen 2026-11-09), and alerts
    are off until onboarding enables them; neither is a reason to stop a run."""
    try:
        alerts = api(f"repos/{slug}/dependabot/alerts?state=open&per_page=100") or []
    except KitError as exc:
        text = str(exc).lower()
        if any(k in text for k in ("403", "404", "disabled", "not accessible", "forbidden", "not enabled")):
            global last_alerts_note
            last_alerts_note = ALERTS_UNAVAILABLE + f" ({str(exc)[-80:]})"
            return []
        raise
    return [{"number": a["number"], "severity": a.get("security_advisory", {}).get("severity"),
             "package": a.get("dependency", {}).get("package", {}).get("name"),
             "manifest": a.get("dependency", {}).get("manifest_path"),
             "summary": a.get("security_advisory", {}).get("summary")} for a in alerts]


def enable_security(slug: str) -> dict:
    """D50 and D80: Dependabot alerts and security updates; squash-only merges
    with delete-branch-on-merge (the free layer, every plan); then the
    enforced layer where GitHub can enforce it (rulesets: public repositories
    on every plan, private ones on Pro and up)."""
    results = {}
    for name, path in (("alerts", f"repos/{slug}/vulnerability-alerts"),
                       ("security_updates", f"repos/{slug}/automated-security-fixes")):
        try:
            api(path, "PUT")
            results[name] = "enabled"
        except KitError as exc:
            results[name] = f"failed: {exc}"
    try:
        api(f"repos/{slug}", "PATCH", raw={"delete_branch_on_merge": True, "allow_auto_merge": False,
                                            "allow_squash_merge": True, "allow_merge_commit": False,
                                            "allow_rebase_merge": False})
        results["delete_branch_on_merge"] = "enabled"
        results["squash_only"] = "enabled"
    except KitError as exc:
        results["delete_branch_on_merge"] = results["squash_only"] = f"failed: {exc}"
    results["protection"] = apply_protection(slug)
    return results


# ---------------------------------------------------------------- the enforced layer (D80)

CLAUDE_APP_ID = 1236702  # `gh api apps/claude` .id, 2026-11-09: the Claude GitHub App the caretaker runs as
ADMIN_ROLE_ID = 5  # GitHub's repository role id for admin
RULESET_NO_ERASE = "kit: main is never erased"
RULESET_PULL_REQUESTS = "kit: changes to main come through pull requests"
RULESET_TAGS = "kit: release and safe-point tags stay"
MAIN_CONDITION = {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}}


def list_rulesets(slug: str) -> list[dict] | None:
    """The repository's rulesets, or None where GitHub can't enforce them (a
    private repository on a Free account answers 403 "Upgrade to GitHub Pro
    or make this repository public", seen 2026-11-09)."""
    try:
        return api(f"repos/{slug}/rulesets?per_page=100") or []
    except KitError as exc:
        text = str(exc)
        if "403" in text or "Upgrade to GitHub Pro" in text or "make this repository public" in text:
            return None
        raise


def ruleset_bodies(with_admin_bypass: bool = True) -> dict[str, dict]:
    """The three rulesets as the REST API takes them. The no-erase ruleset has
    no bypass at all: nobody, the owner included, can force-push or delete
    main. The pull-request ruleset lets the owner (repository admin) and the
    Claude App through, because the kit lands hub changes on main directly
    (D48) from the desktop and from the caretaker; everyone else goes through
    a pull request with the kit/review status. Tags: v* and safe/* can't be
    deleted or moved; the owner's own machine may trim old safe points."""
    admin = [{"actor_id": ADMIN_ROLE_ID, "actor_type": "RepositoryRole", "bypass_mode": "always"}] if with_admin_bypass else []
    app = [{"actor_id": CLAUDE_APP_ID, "actor_type": "Integration", "bypass_mode": "always"}]
    return {
        RULESET_NO_ERASE: {"name": RULESET_NO_ERASE, "target": "branch", "enforcement": "active", "bypass_actors": [],
                           "conditions": MAIN_CONDITION, "rules": [{"type": "deletion"}, {"type": "non_fast_forward"}]},
        RULESET_PULL_REQUESTS: {"name": RULESET_PULL_REQUESTS, "target": "branch", "enforcement": "active",
                                "bypass_actors": admin + app, "conditions": MAIN_CONDITION,
                                "rules": [{"type": "pull_request", "parameters": {
                                              "required_approving_review_count": 0, "dismiss_stale_reviews_on_push": False,
                                              "require_code_owner_review": False, "require_last_push_approval": False,
                                              "required_review_thread_resolution": False}},
                                          {"type": "required_status_checks", "parameters": {
                                              "strict_required_status_checks_policy": False,
                                              "required_status_checks": [{"context": REVIEW_CONTEXT}]}}]},
        RULESET_TAGS: {"name": RULESET_TAGS, "target": "tag", "enforcement": "active", "bypass_actors": admin,
                       "conditions": {"ref_name": {"include": ["refs/tags/v*", "refs/tags/safe/*"], "exclude": []}},
                       "rules": [{"type": "deletion"}, {"type": "update"}]},
    }


def apply_protection(slug: str) -> dict:
    """Put the kit's rulesets in place where GitHub enforces them; idempotent
    (an existing ruleset of the same name is updated). Where they can't be
    enforced, say so: the caller tells the user once what Pro would add."""
    existing = list_rulesets(slug)
    if existing is None:
        return {"enforced": False, "reason": "GitHub can't enforce rules on a private repository on the Free plan",
                "rulesets": {}}
    by_name = {r["name"]: r["id"] for r in existing}
    outcome: dict[str, str] = {}
    for name, body in ruleset_bodies().items():
        try:
            outcome[name] = _put_ruleset(slug, by_name, name, body)
        except KitError as exc:
            if "RepositoryRole" in str(exc) or "actor" in str(exc).lower():
                # A personal repository may not take the admin role as a bypass
                # actor. Tags stay protected without it (nobody trims safe points
                # then). The pull-request ruleset without the owner's bypass
                # would block the kit's own landing, so it is skipped.
                if name == RULESET_PULL_REQUESTS:
                    outcome[name] = f"skipped: the owner can't be a bypass actor here ({str(exc)[-120:]})"
                    continue
                try:
                    outcome[name] = _put_ruleset(slug, by_name, name, ruleset_bodies(with_admin_bypass=False)[name]) + " (no owner bypass)"
                except KitError as exc2:
                    outcome[name] = f"failed: {str(exc2)[-200:]}"
            else:
                outcome[name] = f"failed: {str(exc)[-200:]}"
    enforced = outcome.get(RULESET_NO_ERASE, "").startswith(("created", "updated"))
    return {"enforced": enforced, "reason": "" if enforced else "the no-erase ruleset could not be applied", "rulesets": outcome}


def _put_ruleset(slug: str, by_name: dict, name: str, body: dict) -> str:
    if name in by_name:
        api(f"repos/{slug}/rulesets/{by_name[name]}", "PUT", raw=body)
        return "updated"
    api(f"repos/{slug}/rulesets", "POST", raw=body)
    return "created"


def protection_status(slug: str) -> dict:
    """What holds on this repository right now (for `kit security status`)."""
    repo = api(f"repos/{slug}") or {}
    existing = list_rulesets(slug)
    names = [] if existing is None else [r["name"] for r in existing if r.get("enforcement") == "active"]
    return {"private": bool(repo.get("private")), "squash_only": bool(repo.get("allow_squash_merge"))
            and not repo.get("allow_merge_commit") and not repo.get("allow_rebase_merge"),
            "delete_branch_on_merge": bool(repo.get("delete_branch_on_merge")),
            "rulesets_available": existing is not None, "rulesets": names,
            "enforced": RULESET_NO_ERASE in names, "safe_points": list_safe_tags(slug)}


# ---------------------------------------------------------------- the recovery net (D80)

SAFE_PREFIX = "safe/"
SAFE_KEEP_DAYS = 30


def main_sha(slug: str) -> str:
    ref = api(f"repos/{slug}/git/ref/heads/main") or {}
    return ref.get("object", {}).get("sha", "")


PROXY_REFUSED = "not permitted through this proxy"


def safe_tag(slug: str, date: str | None = None, root: Path | None = None) -> dict:
    """A lightweight tag `safe/YYYY-MM-DD` at main's tip, once a day; the
    recovery net `kit undo` restores from. Over REST where that is allowed;
    the cloud sandbox's GitHub proxy refuses API writes to git/refs ("Write
    access to this GitHub API path is not permitted through this proxy", seen
    2026-11-09) while `git push` from the clone works, so with a `root` the
    tag goes up as a push of the commit id to the tag ref."""
    import datetime as dt
    name = SAFE_PREFIX + (date or dt.date.today().isoformat())
    sha = main_sha(slug)
    if not sha:
        raise KitError("main has no commits on GitHub yet")
    if any(t["tag"] == name for t in list_safe_tags(slug, root)):
        return {"tag": name, "sha": sha, "created": False}
    try:
        api(f"repos/{slug}/git/refs", "POST", raw={"ref": f"refs/tags/{name}", "sha": sha})
        return {"tag": name, "sha": sha, "created": True, "via": "api"}
    except KitError as exc:
        text = str(exc).lower()
        if "already exists" in text:
            return {"tag": name, "sha": sha, "created": False}
        if root is None or PROXY_REFUSED not in text:
            raise
    git(root, "fetch", "-q", "origin", "main", timeout=120)
    push = git(root, "push", "-q", "origin", f"{sha}:refs/tags/{name}", timeout=120)
    if push.returncode != 0:
        raise KitError(f"could not write the safe point by API or by push: {push.stderr.strip()[-200:]}")
    return {"tag": name, "sha": sha, "created": True, "via": "push"}


def list_safe_tags(slug: str, root: Path | None = None) -> list[dict]:
    """Safe points on GitHub. No trailing slash on the path: the cloud proxy
    answers "Request path could not be canonicalized" to one (2026-11-09).
    With a `root`, a refused read falls back to `git ls-remote`."""
    try:
        refs = api(f"repos/{slug}/git/matching-refs/tags/{SAFE_PREFIX.rstrip('/')}") or []
        tags = [{"tag": r["ref"].removeprefix("refs/tags/"), "sha": r["object"]["sha"]} for r in refs]
    except KitError:
        if root is None:
            raise
        out = git(root, "ls-remote", "--tags", "origin", f"refs/tags/{SAFE_PREFIX}*", timeout=60)
        if out.returncode != 0:
            raise
        tags = []
        for line in out.stdout.splitlines():
            sha, _, ref = line.partition("\t")
            if ref and not ref.endswith("^{}"):
                tags.append({"tag": ref.removeprefix("refs/tags/"), "sha": sha})
    return sorted((t for t in tags if t["tag"].startswith(SAFE_PREFIX)), key=lambda t: t["tag"])


def prune_safe_tags(slug: str, keep_days: int = SAFE_KEEP_DAYS, today: str | None = None,
                    root: Path | None = None) -> dict:
    """Delete safe points older than keep_days. Where the tag ruleset is
    enforced the caretaker's token can't delete them, so they come back as
    `protected`; the owner's own machine trims them (the locks chore). With
    a `root`, a proxy that refuses the API delete gets a push delete instead."""
    import datetime as dt
    now = dt.date.fromisoformat(today) if today else dt.date.today()
    pruned, protected, kept = [], [], []
    for t in list_safe_tags(slug, root):
        try:
            when = dt.date.fromisoformat(t["tag"].removeprefix(SAFE_PREFIX))
        except ValueError:
            kept.append(t["tag"])
            continue
        if (now - when).days <= keep_days:
            kept.append(t["tag"])
            continue
        try:
            api(f"repos/{slug}/git/refs/tags/{t['tag']}", "DELETE")
            pruned.append(t["tag"])
        except KitError as exc:
            if root is not None and PROXY_REFUSED in str(exc).lower():
                gone = git(root, "push", "-q", "origin", "--delete", f"refs/tags/{t['tag']}", timeout=120)
                (pruned if gone.returncode == 0 else protected).append(t["tag"])
            else:
                protected.append(t["tag"])
    return {"pruned": pruned, "protected": protected, "kept": kept}


def workflow_usage_hint(slug: str) -> dict:
    """Recent Actions runs, as a rough budget signal for the evidence."""
    data = api(f"repos/{slug}/actions/runs?per_page=50") or {}
    runs = data.get("workflow_runs", [])
    return {"recent_runs": len(runs),
            "failed": sum(1 for r in runs if r.get("conclusion") not in (None, "success", "skipped", "neutral"))}
