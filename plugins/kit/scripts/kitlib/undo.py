"""The recovery net's other half (D80): `kit undo` puts main back to a safe
point, as a new commit on top of history. Never a force-push, never a
deletion: the old commits stay, so an undo can itself be undone.

Where the owner's token may push main (the free layer, or the enforced layer
with the owner's bypass), the restoring commit goes straight to main. Where a
rule refuses the push, the same commit goes up on an `undo/<date>` branch
with a pull request and the kit/review status; the caretaker merges it when
the checks are green.
"""

from __future__ import annotations

import re
from pathlib import Path

from . import github, landing
from .common import GIT_ENV, KitError, git

SAFE_RE = re.compile(r"^safe/\d{4}-\d{2}-\d{2}$")


def list_points(root: Path) -> dict:
    """Safe points on origin, oldest first, plus whether main matches one."""
    out = git(root, "ls-remote", "--tags", "origin", "refs/tags/safe/*", timeout=60)
    if out.returncode != 0:
        raise KitError(f"could not read the safe points on GitHub: {out.stderr.strip()[-200:]}")
    points = []
    for line in out.stdout.splitlines():
        sha, _, ref = line.partition("\t")
        if ref.endswith("^{}"):
            continue
        points.append({"tag": ref.removeprefix("refs/tags/"), "sha": sha})
    points.sort(key=lambda p: p["tag"])
    head = git(root, "rev-parse", "HEAD", timeout=10).stdout.strip()
    return {"points": points, "main": head[:12], "main_is_at": [p["tag"] for p in points if p["sha"] == head]}


def undo(root: Path, to: str, open_pr=None) -> dict:
    if not SAFE_RE.match(to):
        raise KitError("say which safe point, like safe/2026-11-09 (kit undo list shows them)")
    branch = landing.ensure_main(root)
    if branch != "main":
        raise KitError(f"the workspace is on '{branch}', not main")
    if landing.changed_paths(root):
        raise KitError("there are unsaved changes; run `kit land` first so nothing is lost, then undo")
    fetch = git(root, "fetch", "-q", "origin", "main", f"+refs/tags/{to}:refs/tags/{to}", timeout=120)
    if fetch.returncode != 0:
        raise KitError(f"no safe point called {to} on GitHub ({fetch.stderr.strip()[-160:]})")
    local = git(root, "rev-parse", "main", timeout=10).stdout.strip()
    remote = git(root, "rev-parse", "origin/main", timeout=10).stdout.strip()
    if local != remote:
        raise KitError("main here differs from GitHub's copy; run `kit sync` first, then undo")
    target_tree = git(root, "rev-parse", f"{to}^{{tree}}", timeout=10, check=True).stdout.strip()
    if git(root, "rev-parse", "main^{tree}", timeout=10).stdout.strip() == target_tree:
        return {"undone": False, "to": to, "reason": f"main already matches {to}"}
    message = f"Undo: main as it was at {to}"
    commit = git(root, "commit-tree", target_tree, "-p", local, "-m", message, env=GIT_ENV, timeout=30, check=True).stdout.strip()

    git(root, "update-ref", "refs/heads/main", commit, local, timeout=10, check=True)
    git(root, "reset", "-q", "--hard", "main", timeout=60, check=True)  # the tree was clean; this only refreshes it
    push = git(root, "push", "-q", "origin", "main", timeout=120)
    if push.returncode == 0:
        return {"undone": True, "to": to, "commit": commit[:12], "via": "main",
                "previous": local[:12], "note": f"history kept; `kit undo --to <a later safe point>` reverses this"}

    # A rule refused the push (someone without the owner's bypass): go through a pull request.
    git(root, "update-ref", "refs/heads/main", local, commit, timeout=10, check=True)
    git(root, "reset", "-q", "--hard", "main", timeout=60, check=True)
    slug = github.repo_slug(root)
    undo_branch = f"undo/{to.removeprefix('safe/')}"
    git(root, "update-ref", f"refs/heads/{undo_branch}", commit, timeout=10, check=True)
    pushed = git(root, "push", "-q", "-u", "origin", undo_branch, timeout=120)
    if pushed.returncode != 0:
        raise KitError(f"GitHub refused both main and {undo_branch}: {pushed.stderr.strip()[-200:]}")
    body = (f"Restores `main` to the safe point `{to}` as a new commit; nothing in the history is removed. "
            "Opened by `kit undo` because a rule on main refused a direct push.")
    pr = (open_pr or github.open_pr)(slug, undo_branch, message, body)
    github.post_review_status(slug, pr["sha"], "success", f"restores main to {to}; no new code to review")
    return {"undone": False, "to": to, "commit": commit[:12], "via": "pull_request", "pr": pr,
            "note": "main's rule asked for a pull request; it merges when the checks are green (the caretaker does that)"}
