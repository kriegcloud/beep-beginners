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
            return []
        raise
    return [{"number": a["number"], "severity": a.get("security_advisory", {}).get("severity"),
             "package": a.get("dependency", {}).get("package", {}).get("name"),
             "manifest": a.get("dependency", {}).get("manifest_path"),
             "summary": a.get("security_advisory", {}).get("summary")} for a in alerts]


def enable_security(slug: str) -> dict:
    """Dependabot alerts and security updates, plus delete-branch-on-merge (D50)."""
    results = {}
    for name, path in (("alerts", f"repos/{slug}/vulnerability-alerts"),
                       ("security_updates", f"repos/{slug}/automated-security-fixes")):
        try:
            api(path, "PUT")
            results[name] = "enabled"
        except KitError as exc:
            results[name] = f"failed: {exc}"
    try:
        api(f"repos/{slug}", "PATCH", raw={"delete_branch_on_merge": True, "allow_auto_merge": False})
        results["delete_branch_on_merge"] = "enabled"
    except KitError as exc:
        results["delete_branch_on_merge"] = f"failed: {exc}"
    return results


def workflow_usage_hint(slug: str) -> dict:
    """Recent Actions runs, as a rough budget signal for the evidence."""
    data = api(f"repos/{slug}/actions/runs?per_page=50") or {}
    runs = data.get("workflow_runs", [])
    return {"recent_runs": len(runs),
            "failed": sum(1 for r in runs if r.get("conclusion") not in (None, "success", "skipped", "neutral"))}
