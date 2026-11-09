"""Landing changes (D48): hub paths commit to main, project paths go to a
goal branch, and the kit decides which by what changed.

The working tree stays on main the whole time. Project commits are built
with a temporary index (read-tree, add, write-tree, commit-tree, update-ref),
so the tree on disk is never switched. Local bookkeeping about what was last
landed per project lives under .git/kit/, never in the repository.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

from .common import GIT_ENV, KitError, git, kit_state_dir, read_json, run, write_json

PROJECTS = "projects"
DEFAULT_MESSAGE = "Save work from a session"

# Token shapes gitleaks would catch; used only when gitleaks itself is absent,
# so the guard is never fully blind.
_FALLBACK_SECRETS = [
    re.compile(p) for p in (
        r"ghp_[A-Za-z0-9]{36}", r"github_pat_[A-Za-z0-9_]{60,}", r"gho_[A-Za-z0-9]{36}",
        r"sk-[A-Za-z0-9_-]{32,}", r"sk-ant-[A-Za-z0-9_-]{32,}", r"AKIA[0-9A-Z]{16}",
        r"xox[abpr]-[A-Za-z0-9-]{20,}", r"-----BEGIN (RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----",
        r"glpat-[A-Za-z0-9_-]{20}", r"AIza[0-9A-Za-z_-]{35}",
    )
]


# ---------------------------------------------------------------- status

def changed_paths(root: Path) -> list[str]:
    """Paths with any change (tracked or untracked, never ignored)."""
    out = git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all", timeout=30, check=True)
    paths: list[str] = []
    fields = out.stdout.split("\0")
    i = 0
    while i < len(fields):
        entry = fields[i]
        if not entry:
            i += 1
            continue
        status, path = entry[:2], entry[3:]
        if status.startswith("R") or status.startswith("C"):
            # rename: "R  new\0old"
            paths.append(path)
            i += 1
            if i < len(fields):
                paths.append(fields[i])
        else:
            paths.append(path)
        i += 1
    return sorted(set(p for p in paths if p))


def partition(paths: list[str]) -> tuple[list[str], dict[str, list[str]]]:
    hub: list[str] = []
    projects: dict[str, list[str]] = {}
    for p in paths:
        parts = p.split("/")
        if len(parts) >= 3 and parts[0] == PROJECTS:
            projects.setdefault(parts[1], []).append(p)
        else:
            hub.append(p)
    return hub, projects


def current_branch(root: Path) -> str:
    return git(root, "rev-parse", "--abbrev-ref", "HEAD", timeout=10).stdout.strip()


def project_meta(root: Path, name: str) -> dict:
    return read_json(root / PROJECTS / name / ".kit.json", {})


def branch_for(root: Path, name: str) -> str:
    meta = project_meta(root, name)
    goal = meta.get("goal")
    return f"goal/{goal}" if goal else f"project/{name}"


# ---------------------------------------------------------------- secrets

def gitleaks_available() -> bool:
    return run(["gitleaks", "version"], timeout=20).returncode == 0


def scan_paths(root: Path, paths: list[str]) -> dict:
    """Scan the given working-tree paths for secrets. Returns {ok, tool, findings}."""
    files = [root / p for p in paths if (root / p).is_file()]
    if not files:
        return {"ok": True, "tool": "none", "findings": []}
    if gitleaks_available():
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "report.json"
            # Scan a staging copy of just these files so untouched history never slows a checkpoint.
            stage = Path(tmp) / "stage"
            for f in files:
                dest = stage / f.relative_to(root)
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(f.read_bytes())
            out = run(["gitleaks", "dir", str(stage), "--no-banner", "--redact", "--exit-code", "2",
                       "--report-format", "json", "--report-path", str(report)], timeout=120)
            findings = []
            if report.exists():
                try:
                    for item in json.loads(report.read_text(encoding="utf-8") or "[]"):
                        rel = str(Path(item.get("File", "")).resolve().relative_to(stage.resolve())) if item.get("File") else ""
                        findings.append({"file": rel.replace(os.sep, "/"), "rule": item.get("RuleID"),
                                         "line": item.get("StartLine")})
                except (json.JSONDecodeError, ValueError):
                    pass
            if out.returncode == 2 and not findings:
                findings.append({"file": "?", "rule": "gitleaks", "line": None})
            return {"ok": out.returncode == 0, "tool": "gitleaks", "findings": findings}
    findings = []
    for f in files:
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for rx in _FALLBACK_SECRETS:
            m = rx.search(text)
            if m:
                findings.append({"file": str(f.relative_to(root)).replace(os.sep, "/"), "rule": rx.pattern[:24],
                                 "line": text.count("\n", 0, m.start()) + 1})
                break
    return {"ok": not findings, "tool": "builtin", "findings": findings}


# ---------------------------------------------------------------- state

def landed_state(root: Path) -> dict:
    return read_json(kit_state_dir(root) / "landed.json", {"projects": {}})


def save_landed(root: Path, state: dict) -> None:
    write_json(kit_state_dir(root) / "landed.json", state)


# ---------------------------------------------------------------- trees

def tree_of_prefix(root: Path, revision: str, prefix: str) -> str | None:
    """Tree sha of `prefix` in `revision`, or None when absent."""
    out = git(root, "rev-parse", "--verify", "--quiet", f"{revision}:{prefix}", timeout=10)
    return out.stdout.strip() or None


def working_tree_of_prefix(root: Path, prefix: str) -> str | None:
    """Tree sha of the working tree's `prefix`, built in a temporary index."""
    folder = root / prefix
    if not folder.exists():
        return None
    with tempfile.TemporaryDirectory() as tmp:
        env = {**GIT_ENV, "GIT_INDEX_FILE": str(Path(tmp) / "index")}
        git(root, "add", "-A", "--force", "--", prefix, env=env, timeout=60, check=True)
        out = git(root, "write-tree", f"--prefix={prefix}/", env=env, timeout=30)
        return out.stdout.strip() or None


def _commit_project(root: Path, name: str, branch: str, message: str) -> dict:
    """Commit the working tree's projects/<name> onto `branch` without touching
    the checkout. The parent is the branch tip when it exists, else main."""
    prefix = f"{PROJECTS}/{name}"
    exists = git(root, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}", timeout=10).returncode == 0
    remote = git(root, "rev-parse", "--verify", "--quiet", f"refs/remotes/origin/{branch}", timeout=10)
    if not exists and remote.returncode == 0:
        git(root, "update-ref", f"refs/heads/{branch}", remote.stdout.strip(), timeout=10, check=True)
        exists = True
    base = branch if exists else "HEAD"
    with tempfile.TemporaryDirectory() as tmp:
        env = {**GIT_ENV, "GIT_INDEX_FILE": str(Path(tmp) / "index")}
        git(root, "read-tree", base, env=env, timeout=30, check=True)
        # Drop whatever the base has under the prefix, then add the working tree's version.
        git(root, "rm", "-r", "-q", "--cached", "--ignore-unmatch", "--", prefix, env=env, timeout=60)
        git(root, "add", "-A", "--force", "--", prefix, env=env, timeout=60, check=True)
        tree = git(root, "write-tree", env=env, timeout=30, check=True).stdout.strip()
    base_tree = git(root, "rev-parse", f"{base}^{{tree}}", timeout=10).stdout.strip()
    if tree == base_tree:
        return {"project": name, "branch": branch, "committed": False, "reason": "no change since the branch tip"}
    parent = git(root, "rev-parse", base, timeout=10).stdout.strip()
    commit = git(root, "commit-tree", tree, "-p", parent, "-m", message, timeout=30, check=True).stdout.strip()
    git(root, "update-ref", f"refs/heads/{branch}", commit, timeout=10, check=True)
    state = landed_state(root)
    state["projects"][name] = {"branch": branch, "tree": tree_of_prefix(root, commit, prefix), "commit": commit}
    save_landed(root, state)
    return {"project": name, "branch": branch, "committed": True, "commit": commit[:12]}


# ---------------------------------------------------------------- land

def land(root: Path, message: str | None = None, allow_secrets: bool = False) -> dict:
    branch = current_branch(root)
    if branch != "main":
        raise KitError(f"the workspace is on '{branch}', not main; landing only works from main")
    message = (message or DEFAULT_MESSAGE).strip()
    paths = changed_paths(root)
    if not paths:
        return {"landed": False, "reason": "nothing changed", "hub": [], "projects": []}
    hub, projects = partition(paths)

    scan = scan_paths(root, paths)
    if not scan["ok"] and not allow_secrets:
        names = ", ".join(sorted({f["file"] for f in scan["findings"]}))
        raise KitError("a file looks like it holds a secret, so nothing was saved: "
                       f"{names}. Move the secret to 1Password (op://...) and remove it from the file.")

    result: dict = {"landed": True, "message": message, "secrets": scan, "hub": [], "projects": []}
    if any(p.startswith("docs/") and p.endswith(".md") and not p.endswith(("/log.md", "/index.md")) for p in hub):
        from . import okf
        okf.log_append(root / "docs", f"**Update** {message}")
        okf.write_indexes(root)
        hub = sorted(set(hub) | {p for p in changed_paths(root) if p.startswith("docs/")})
    if hub:
        git(root, "add", "-A", "--", *hub, timeout=60, check=True)
        staged = git(root, "diff", "--cached", "--quiet", timeout=30).returncode == 1
        if staged:
            git(root, "commit", "-q", "-m", message, timeout=60, check=True)
            result["hub"] = hub
            result["hub_commit"] = git(root, "rev-parse", "--short", "HEAD", timeout=10).stdout.strip()
    for name in sorted(projects):
        result["projects"].append(_commit_project(root, name, branch_for(root, name), message))
    return result


# ---------------------------------------------------------------- sync

def has_origin(root: Path) -> bool:
    return git(root, "remote", "get-url", "origin", timeout=10).returncode == 0


def unpushed(root: Path, branch: str) -> int:
    remote = git(root, "rev-parse", "--verify", "--quiet", f"refs/remotes/origin/{branch}", timeout=10)
    if remote.returncode != 0:
        return int(git(root, "rev-list", "--count", branch, timeout=20).stdout.strip() or 0)
    return int(git(root, "rev-list", "--count", f"origin/{branch}..{branch}", timeout=20).stdout.strip() or 0)


def _materialize(root: Path, prefix: str, revision: str | None) -> None:
    """Make the working tree's `prefix` equal to `revision`'s (or empty)."""
    folder = root / prefix
    wanted: set[str] = set()
    if revision and tree_of_prefix(root, revision, prefix):
        out = git(root, "ls-tree", "-r", "--name-only", revision, "--", prefix, timeout=30, check=True)
        wanted = {line for line in out.stdout.splitlines() if line}
    if folder.exists():
        for path in sorted(folder.rglob("*"), reverse=True):
            rel = str(path.relative_to(root)).replace(os.sep, "/")
            if path.is_file() and rel not in wanted:
                path.unlink()
            elif path.is_dir() and not any(path.iterdir()):
                path.rmdir()
    if wanted:
        git(root, "checkout", revision, "--", prefix, timeout=60, check=True)
    # Reflect the result in the index so `git status` matches the tree on disk.
    git(root, "reset", "-q", "--", prefix, timeout=30)


def _reconcile(root: Path, name: str, branch: str, local_sha: str, remote_sha: str) -> str:
    """Both this computer and the caretaker added commits to the branch. Merge
    them without touching the checkout (git merge-tree, git 2.38+). A real
    conflict becomes a NEEDS-YOU item in plain words (D69)."""
    out = git(root, "merge-tree", "--write-tree", local_sha, remote_sha, timeout=60)
    if out.returncode == 0 and out.stdout.strip():
        tree = out.stdout.strip().splitlines()[0]
        commit = git(root, "commit-tree", tree, "-p", local_sha, "-p", remote_sha,
                     "-m", f"Bring together this computer's and the caretaker's work on {name}", timeout=30, check=True).stdout.strip()
        git(root, "update-ref", f"refs/heads/{branch}", commit, timeout=10, check=True)
        return f"brought together two versions of {name}"
    from . import needs_you
    brief = (f"**What I'm deciding.** Your work on {name} and the caretaker's fix changed the same lines, and I can't tell which "
             f"version you want.\n\n**Your options.**\n- Keep your version\n- Keep the caretaker's version\n- Look at both together with me\n\n"
             f"**What each costs you.**\n- Your version: the caretaker's fix is redone later\n- The caretaker's: your last edit to those lines is redone\n"
             f"- Both: ten minutes with me\n\n**What I recommend, and why.** Look at both together; it's usually one or two lines.\n\n"
             f"**What you'd have to do.** Say which, and I'll do the rest.")
    try:
        if not any(i.get("kind") == "conflict" and name in i.get("title", "") for i in needs_you.load(root)["open"]):
            needs_you.add(root, f"Two versions of {name} need your pick", brief, source="kit sync", kind="conflict")
    except KitError:
        pass
    return f"conflict in {name}: both this computer and the caretaker changed it; asked in NEEDS-YOU"


def sync(root: Path, at: str = "start", open_pr=None) -> dict:
    """Reconcile project branches, pull main, push everything.

    `open_pr(root, branch, project)` is called for a pushed branch with no PR;
    it comes from the pr module so this one stays free of GitHub calls.
    """
    report: dict = {"at": at, "notes": [], "pushed": [], "prs": []}
    if current_branch(root) != "main":
        report["notes"].append("not on main; sync skipped")
        return report
    state = landed_state(root)

    # 1. Unsaved project edits from a session that ended badly: land them first.
    for name in sorted(state.get("projects", {})):
        prefix = f"{PROJECTS}/{name}"
        working = working_tree_of_prefix(root, prefix)
        if working and working != state["projects"][name].get("tree"):
            report["notes"].append(f"saved unfinished work in {name}")
            land(root, "Save unfinished work from an earlier session")
            state = landed_state(root)

    online = has_origin(root)
    if online:
        fetch = git(root, "fetch", "--prune", "--quiet", "origin", timeout=90)
        if fetch.returncode != 0:
            report["notes"].append("could not reach GitHub; working offline")
            online = False

    # 2. Put each project folder back to main's version so main can move.
    for name in sorted(state.get("projects", {})):
        _materialize(root, f"{PROJECTS}/{name}", "HEAD")

    # 3. Bring main up to date.
    if online:
        pull = git(root, "merge", "--ff-only", "--quiet", "origin/main", timeout=60)
        if pull.returncode != 0:
            report["notes"].append("main on GitHub has changes that don't line up with this computer's; left as is")

    # 4. Re-apply open branches, drop merged ones.
    for name in sorted(state.get("projects", {})):
        prefix = f"{PROJECTS}/{name}"
        info = state["projects"][name]
        branch = info["branch"]
        if online:
            remote_ref = git(root, "rev-parse", "--verify", "--quiet", f"refs/remotes/origin/{branch}", timeout=10)
            if remote_ref.returncode == 0:
                remote_sha = remote_ref.stdout.strip()
                local_sha = git(root, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}", timeout=10).stdout.strip()
                if local_sha and local_sha != remote_sha:
                    behind = git(root, "merge-base", "--is-ancestor", local_sha, remote_sha, timeout=20).returncode == 0
                    ahead = git(root, "merge-base", "--is-ancestor", remote_sha, local_sha, timeout=20).returncode == 0
                    if behind:
                        git(root, "update-ref", f"refs/heads/{branch}", remote_sha, timeout=10)
                    elif not ahead:
                        outcome = _reconcile(root, name, branch, local_sha, remote_sha)
                        report["notes"].append(outcome)
                        if outcome.startswith("conflict"):
                            report.setdefault("conflicts", []).append(name)
                            _materialize(root, prefix, "HEAD")
                            continue
                elif not local_sha:
                    git(root, "update-ref", f"refs/heads/{branch}", remote_sha, timeout=10)
        merged = git(root, "merge-base", "--is-ancestor", branch, "HEAD", timeout=20).returncode == 0
        if merged:
            report["notes"].append(f"{name} landed on main")
            git(root, "branch", "-d", "-q", branch, timeout=20)
            del state["projects"][name]
            continue
        _materialize(root, prefix, branch)
        info["tree"] = tree_of_prefix(root, branch, prefix)
        info["commit"] = git(root, "rev-parse", branch, timeout=10).stdout.strip()
    save_landed(root, state)

    # 5. Push.
    if online:
        if unpushed(root, "main") > 0:
            push = git(root, "push", "--quiet", "origin", "main", timeout=90)
            report["pushed"].append({"branch": "main", "ok": push.returncode == 0,
                                     "error": (push.stderr.strip().splitlines() or [""])[-1] if push.returncode else ""})
        for name, info in sorted(state.get("projects", {}).items()):
            branch = info["branch"]
            if unpushed(root, branch) > 0:
                push = git(root, "push", "--quiet", "-u", "origin", branch, timeout=90)
                report["pushed"].append({"branch": branch, "ok": push.returncode == 0,
                                         "error": (push.stderr.strip().splitlines() or [""])[-1] if push.returncode else ""})
            if open_pr is not None:
                try:
                    pr = open_pr(root, branch, name)
                    if pr:
                        report["prs"].append(pr)
                except KitError as exc:
                    report["notes"].append(f"could not open the pull request for {name}: {exc}")
    else:
        report["notes"].append("no GitHub copy reachable; nothing pushed")
    return report
