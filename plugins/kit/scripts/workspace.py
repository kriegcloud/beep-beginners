# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Create the user's private workspace on GitHub from the template and their profile.

  workspace.py create --parent DIR [--name workspace] [--answers FILE] [--user-name NAME] [--no-github]
  workspace.py user-settings                  auto mode, Opus 5.5 medium, in ~/.claude/settings.json
  workspace.py git-identity --name NAME       set git name and a private GitHub email
  workspace.py cloud-ready                    facts the caretaker step needs: repo url, owner, timezone offset

The workspace starts as a copy of ../template. `--answers` is the profile JSON
the onboarding skill drafted (see `kit profile draft`); it fills the AGENTS.md
slots and writes the user's personal skills. The private repo is created with
the signed-in GitHub CLI. Nothing is pushed anywhere but the new repo's origin.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLUGIN = HERE.parent
TEMPLATE = PLUGIN / "template"
sys.path.insert(0, str(HERE))
from state import load_state, save_state  # noqa: E402

MODEL = "claude-opus-5-5"
EFFORT = "medium"
GIT_ENV = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
KIT = HERE / "kit.py"


def run(argv: list[str], cwd: Path | None = None, check: bool = True, timeout: float = 300) -> str:
    out = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, env=GIT_ENV, check=False,
                         encoding="utf-8", errors="replace", timeout=timeout)
    if check and out.returncode != 0:
        raise RuntimeError(f"{' '.join(argv[:3])} failed: {(out.stderr or out.stdout).strip()[-400:]}")
    return out.stdout.strip()


def kit(root: Path, *args: str) -> dict:
    out = run(["uv", "run", "--quiet", "--script", str(KIT), "--root", str(root), *args])
    return json.loads(out) if out else {}


def write_config(target: Path, paths: dict) -> None:
    lines = ["# Where this workspace's data lives outside git (decision 5). Paths only.",
             "# Agents read these instead of guessing. Edit a path if a folder moves.", "", "[paths]"]
    for key, value in paths.items():
        lines.append(f"{key} = {json.dumps(value)}")
    (target / "workspace.config").write_text("\n".join(lines) + "\n", encoding="utf-8")


def resolve_paths(paths: dict, facts: dict) -> dict:
    home = facts.get("home") or str(Path.home())
    documents = facts.get("documents") or str(Path(home) / "Documents")
    resolved = {}
    for key, value in paths.items():
        value = str(value).replace("{home}", home).replace("{documents}", documents)
        resolved[key] = str(Path(value)) if value else ""
    return resolved


def marketplace_source() -> str | None:
    """Test runs point the workspace at a local kit checkout instead of GitHub."""
    return os.environ.get("BEEP_BEGINNERS_MARKETPLACE_SOURCE") or None


def install_project_plugins(target: Path) -> dict:
    """Install every plugin the folder's settings enable, at project scope
    (enabling alone left the first session with plugin-cache-miss, test VM 2026-11-07)."""
    settings = json.loads((target / ".claude" / "settings.json").read_text(encoding="utf-8"))
    results: dict[str, str] = {}
    for plugin, enabled in settings.get("enabledPlugins", {}).items():
        if not enabled:
            continue
        out = subprocess.run(["claude", "plugin", "install", plugin, "--scope", "project"],
                             cwd=target, capture_output=True, text=True, check=False,
                             encoding="utf-8", errors="replace", shell=(os.name == "nt"), timeout=300)
        tail = (out.stderr or out.stdout).strip().splitlines()
        results[plugin] = "installed" if out.returncode == 0 else (tail[-1] if tail else f"exit {out.returncode}")
    return results


def init_and_push(target: Path, repo_name: str, message: str, github: bool = True) -> str:
    run(["git", "init", "-q", "-b", "main"], cwd=target)
    run(["git", "add", "-A"], cwd=target)
    run(["git", "commit", "-q", "-m", message], cwd=target)
    if not github:
        return "(local only)"
    login = run(["gh", "api", "user", "--jq", ".login"])
    exists = subprocess.run(["gh", "repo", "view", f"{login}/{repo_name}"], capture_output=True, check=False).returncode == 0
    if exists:
        raise RuntimeError(f"github.com/{login}/{repo_name} already exists; pick another name or remove it first")
    run(["gh", "repo", "create", repo_name, "--private", "--source", str(target), "--remote", "origin", "--push"], cwd=target)
    return f"https://github.com/{login}/{repo_name}"


def create(args: argparse.Namespace) -> dict:
    state = load_state()
    facts = state.get("facts", {})
    answers_state = state.get("answers", {})
    parent = Path(args.parent).expanduser()
    parent.mkdir(parents=True, exist_ok=True)
    target = parent / args.name
    if target.exists() and any(target.iterdir()):
        raise SystemExit(json.dumps({"error": f"{target} already has files in it"}))
    shutil.copytree(TEMPLATE, target, dirs_exist_ok=True)

    settings_path = target / ".claude" / "settings.json"
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    source = marketplace_source()
    if source:
        settings["extraKnownMarketplaces"]["beep-beginners"]["source"] = (
            {"source": "directory", "path": source} if os.path.isdir(source) else {"source": "github", "repo": source})
    else:
        # D72: workspaces track the kit's `stable` branch; the test VM and the
        # maintainer's own workspace set BEEP_BEGINNERS_KIT_REF=main.
        settings["extraKnownMarketplaces"]["beep-beginners"]["source"]["ref"] = os.environ.get("BEEP_BEGINNERS_KIT_REF", "stable")
    settings_path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")

    profile: dict = {}
    if args.answers:
        profile = json.loads(Path(args.answers).read_text(encoding="utf-8"))
    profile.setdefault("name", args.user_name or answers_state.get("name") or facts.get("user") or "the user")
    profile.setdefault("about", f"{profile['name']} is setting this workspace up. Onboarding fills the rest in.")
    profile.setdefault("subscriptions", answers_state.get("subscriptions") or ["claude"])
    helper_name = answers_state.get("helper_name")
    if helper_name and not profile.get("helper"):
        profile["helper"] = {"name": helper_name, "keys_url": answers_state.get("helper_keys_url", "")}
    written = kit(target, "profile", "write", "--answers", _tmp_json(profile))

    write_config(target, resolve_paths(profile.get("paths", {}), facts))
    result = {"workspace": str(target),
              "workspace_url": init_and_push(target, args.name, "Start my workspace", not args.no_github),
              "profile": written}
    result["plugins"] = install_project_plugins(target) if not args.no_github else {}
    if not args.no_github:
        try:
            result["security"] = kit(target, "security", "enable")
        except (RuntimeError, json.JSONDecodeError) as exc:
            result["security"] = {"error": str(exc)[-300:]}

    state.setdefault("answers", {})["workspace"] = str(target)
    state["workspace"] = result
    save_state(state)
    return result


def _tmp_json(data: dict) -> str:
    folder = Path(os.environ.get("BEEP_BEGINNERS_STATE") or Path.home() / ".beep-beginners")
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "profile-answers.json"
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return str(path)


def user_settings(_: argparse.Namespace) -> dict:
    path = Path.home() / ".claude" / "settings.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    current = {}
    if path.exists():
        current = json.loads(path.read_text(encoding="utf-8") or "{}")
        shutil.copy(path, path.with_suffix(".before-beep-beginners.json"))
    current.setdefault("permissions", {})["defaultMode"] = "auto"
    current["model"] = MODEL
    current.setdefault("modelSettings", {}).setdefault(MODEL, {})["effortLevel"] = EFFORT
    path.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
    return {"settings": str(path), "defaultMode": "auto", "model": MODEL, "effort": EFFORT}


def git_identity(args: argparse.Namespace) -> dict:
    user = json.loads(run(["gh", "api", "user"]))
    email = f"{user['id']}+{user['login']}@users.noreply.github.com"
    if not run(["git", "config", "--global", "user.name"], check=False):
        run(["git", "config", "--global", "user.name", args.name])
    if not run(["git", "config", "--global", "user.email"], check=False):
        run(["git", "config", "--global", "user.email", email])
    run(["git", "config", "--global", "init.defaultBranch", "main"])
    return {"name_set": True, "email": "GitHub private address"}


def cloud_ready(_: argparse.Namespace) -> dict:
    """What the caretaker step needs: the workspace url, and the UTC offset so
    the 7:07 local sweep becomes a UTC cron."""
    state = load_state()
    ws = state.get("workspace", {})
    offset = dt.datetime.now().astimezone().utcoffset() or dt.timedelta(0)
    hours = offset.total_seconds() / 3600
    total = (7 * 60 + 7) - int(hours * 60)
    total %= 24 * 60
    url = ws.get("workspace_url", "")
    m = re.search(r"github\.com/([^/]+)/([^/]+)", url)
    return {"workspace_url": url, "owner": m.group(1) if m else "", "repo": m.group(2) if m else "",
            "utc_offset_hours": hours, "sweep_cron_utc": f"{total % 60} {total // 60} * * *",
            "model": MODEL, "effort": EFFORT}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("create"); p.add_argument("--parent", required=True); p.add_argument("--name", default="workspace")
    p.add_argument("--answers"); p.add_argument("--user-name")
    p.add_argument("--no-github", action="store_true", help="local repo only (tests)")
    sub.add_parser("user-settings")
    p = sub.add_parser("git-identity"); p.add_argument("--name", required=True)
    sub.add_parser("cloud-ready")
    args = parser.parse_args()
    handler = {"create": create, "user-settings": user_settings, "git-identity": git_identity, "cloud-ready": cloud_ready}[args.cmd]
    try:
        result = handler(args)
    except RuntimeError as exc:
        print(json.dumps({"error": str(exc)}))
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
