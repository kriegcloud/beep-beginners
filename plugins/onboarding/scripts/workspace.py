# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Create the user's private workspace (and seeded side repos) on GitHub.

  workspace.py create --parent DIR [--name workspace] [--seed ID] [--user-name NAME]
  workspace.py move-code --seed ID            copy scripts from Documents into git
  workspace.py user-settings                  auto mode in ~/.claude/settings.json
  workspace.py git-identity --name NAME       set git name and a private GitHub email

The workspace starts as a copy of ../template, plus the seed's folders and
rules when a seed is chosen. The private repo is created with the signed-in
GitHub CLI. Nothing is pushed anywhere but the new repo's origin.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLUGIN = HERE.parent
TEMPLATE = PLUGIN / "template"
SEEDS = PLUGIN / "seeds"
sys.path.insert(0, str(HERE))
from state import load_state, save_state  # noqa: E402

MODEL = "claude-opus-5-5"
EFFORT = "medium"

GIT_ENV = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}


def run(argv: list[str], cwd: Path | None = None, check: bool = True) -> str:
    out = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, env=GIT_ENV, check=False,
                         encoding="utf-8", errors="replace")
    if check and out.returncode != 0:
        raise RuntimeError(f"{' '.join(argv[:3])} failed: {(out.stderr or out.stdout).strip()[-400:]}")
    return out.stdout.strip()


def load_seed(seed: str | None) -> dict:
    if not seed:
        return {}
    with (SEEDS / seed / "seed.toml").open("rb") as fh:
        return tomllib.load(fh)


def set_slot(text: str, slot: str, body: str) -> str:
    pattern = re.compile(rf"<!-- slot:{slot} -->\n.*?<!-- /slot:{slot} -->", re.S)
    return pattern.sub(lambda _: body.rstrip("\n"), text, count=1)


def resolve_paths(paths: dict, facts: dict) -> dict:
    home = facts.get("home") or str(Path.home())
    documents = facts.get("documents") or str(Path(home) / "Documents")
    resolved = {}
    for key, value in paths.items():
        value = str(value).replace("{home}", home).replace("{documents}", documents)
        resolved[key] = str(Path(value)) if value else ""
    return resolved


def write_config(target: Path, paths: dict) -> None:
    lines = ["# Where this workspace's data lives outside git (decision 5). Paths only.",
             "# Agents read these instead of guessing. Edit a path if a folder moves.", "", "[paths]"]
    for key, value in paths.items():
        lines.append(f"{key} = {json.dumps(value)}")
    (target / "workspace.config").write_text("\n".join(lines) + "\n", encoding="utf-8")


def merge_settings(base: dict, override: dict) -> dict:
    merged = json.loads(json.dumps(base))
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = {**merged[key], **value}
        else:
            merged[key] = value
    return merged


def other_ai_text(subscriptions: list[str]) -> str:
    others = [s for s in subscriptions if s.lower() != "claude"]
    if not others:
        return ""
    names = {"chatgpt": "ChatGPT (Codex CLI)", "grok": "Grok (grok CLI)", "gemini": "Gemini (gemini CLI)"}
    listed = ", ".join(names.get(s.lower(), s) for s in others)
    return f"""## Other AI subscriptions

The user also pays for {listed}. CLIProxyAPI runs at logon on
`http://127.0.0.1:8317` as an agent-only route to those subscriptions.
Route child work through it when the task is long, bulky or repetitive
(research sweeps, bulk rewrites, first drafts, second-opinion reviews), so the
user's Claude limits last for the work only Claude should do. Keep anything
involving money, publishing or the user's accounts on Claude. Never show the
proxy or its config to the user, and never read its config folder.
"""


def install_project_plugins(target: Path) -> dict:
    """Install every plugin the folder's settings enable, at project scope.

    Enabling a plugin in `.claude/settings.json` is not enough on its own: the
    first session in the folder logged `plugin-cache-miss` for each one and
    loaded no skills (test VM, 2026-11-07). An explicit project-scope install
    records them, and the next session loads them."""
    settings = json.loads((target / ".claude" / "settings.json").read_text(encoding="utf-8"))
    results: dict[str, str] = {}
    for plugin, enabled in settings.get("enabledPlugins", {}).items():
        if not enabled:
            continue
        out = subprocess.run(["claude", "plugin", "install", plugin, "--scope", "project"],
                             cwd=target, capture_output=True, text=True, check=False,
                             encoding="utf-8", errors="replace", shell=(os.name == "nt"))
        results[plugin] = "installed" if out.returncode == 0 else (out.stderr or out.stdout).strip().splitlines()[-1:] and (out.stderr or out.stdout).strip().splitlines()[-1] or f"exit {out.returncode}"
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
    answers = state.get("answers", {})
    seed = load_seed(args.seed)
    parent = Path(args.parent).expanduser()
    parent.mkdir(parents=True, exist_ok=True)
    target = parent / args.name
    if target.exists() and any(target.iterdir()):
        raise SystemExit(json.dumps({"error": f"{target} already has files in it"}))
    shutil.copytree(TEMPLATE, target, dirs_exist_ok=True)

    agents = (target / "AGENTS.md").read_text(encoding="utf-8")
    user_name = args.user_name or answers.get("name") or facts.get("user") or "the user"
    if args.seed:
        about = (SEEDS / args.seed / "about.md").read_text(encoding="utf-8").replace("{{name}}", user_name)
        agents = set_slot(agents, "about", f"The user is {user_name}.\n\n{about}")
        folder_lines = []
        for folder in sorted((SEEDS / args.seed / "folders").iterdir()):
            shutil.copytree(folder, target / folder.name, dirs_exist_ok=True)
            text = (folder / "AGENTS.md").read_text(encoding="utf-8")
            paragraph = text.split("\n\n")[1] if "\n\n" in text else ""
            summary = " ".join(paragraph.split())
            folder_lines.append(f"- `{folder.name}/`: {summary} Its own `AGENTS.md` has the rules.")
        agents = set_slot(agents, "folders", "\n".join(folder_lines))
        helper = seed.get("helper", {}).get("name", "your helper")
        agents = set_slot(agents, "helper", f"The user's helper is {helper}. Say \"{helper}\" in messages, not \"your helper\".")
        settings = json.loads((target / ".claude" / "settings.json").read_text(encoding="utf-8"))
        for plugin in seed.get("plugins", {}).get("enable", []):
            settings["enabledPlugins"][plugin] = True
        (target / ".claude" / "settings.json").write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    else:
        agents = set_slot(agents, "about", f"The user is {user_name}.")
        agents = set_slot(agents, "folders", "")
        agents = set_slot(agents, "helper", "")
    agents = set_slot(agents, "other-ai", other_ai_text(answers.get("subscriptions", [])))
    agents = re.sub(r"\n{3,}", "\n\n", agents)
    (target / "AGENTS.md").write_text(agents, encoding="utf-8")

    paths = resolve_paths(seed.get("paths", {}), facts)
    write_config(target, paths)
    result = {"workspace": str(target), "workspace_url": init_and_push(target, args.name, "Start my workspace", not args.no_github)}
    result["plugins"] = install_project_plugins(target)

    for key, repo in seed.get("repos", {}).items():
        side = parent / repo["name"]
        if (side / ".git").exists():
            result[key] = {"path": str(side), "note": "already a git repo, left as is"}
            continue
        shutil.copytree(SEEDS / args.seed / key, side, dirs_exist_ok=True)
        base = json.loads((TEMPLATE / ".claude" / "settings.json").read_text(encoding="utf-8"))
        own = json.loads((side / ".claude" / "settings.json").read_text(encoding="utf-8"))
        merged = merge_settings(base, own)
        merged["enabledPlugins"] = own.get("enabledPlugins", merged["enabledPlugins"])
        (side / ".claude" / "settings.json").write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
        write_config(side, paths)
        result[key] = {"path": str(side), "url": init_and_push(side, repo["name"], "Set up the project folders", not args.no_github),
                       "plugins": install_project_plugins(side)}

    state.setdefault("answers", {})["workspace"] = str(target)
    state["workspace"] = result
    save_state(state)
    return result


def move_code(args: argparse.Namespace) -> dict:
    """Copy code (not data) from Documents into the repos. Originals stay put,
    with a note saying where the git copy lives."""
    state = load_state()
    seed = load_seed(args.seed)
    facts = state.get("facts", {})
    workspace = Path(state["answers"]["workspace"])
    copied: dict[str, list[str]] = {}
    for key, rule in seed.get("move_code", {}).items():
        src = Path(resolve_paths({"x": rule["from"]}, facts)["x"])
        repo = seed.get("repos", {}).get(key)
        dest_root = (workspace.parent / repo["name"]) if repo else workspace
        dest = dest_root / rule["into"] if rule["into"] else dest_root
        if not src.exists():
            copied[key] = []
            continue
        files: list[str] = []
        for pattern in rule["patterns"]:
            for f in src.glob(pattern):
                if f.is_file():
                    out = dest / f.relative_to(src)
                    out.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(f, out)
                    files.append(str(f.relative_to(src)))
        if files:
            (src / "WHERE-THE-CODE-LIVES.txt").write_text(
                f"The scripts from this folder were copied into git on {state.get('updated', '')[:10]}:\n"
                f"{dest}\n\nWork on the copies there. The data files stay here, backed up by OneDrive.\n",
                encoding="utf-8")
            run(["git", "add", "-A"], cwd=dest_root)
            run(["git", "commit", "-q", "-m", f"Bring in the scripts from Documents ({key})"], cwd=dest_root, check=False)
        copied[key] = files
    return {"copied": copied}


def user_settings(_: argparse.Namespace) -> dict:
    path = Path.home() / ".claude" / "settings.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    current = {}
    if path.exists():
        current = json.loads(path.read_text(encoding="utf-8") or "{}")
        shutil.copy(path, path.with_suffix(".before-beep-beginners.json"))
    current.setdefault("permissions", {})["defaultMode"] = "auto"
    # Opus 5.5 at medium effort for every session (operator ruling 2026-11-07):
    # the desktop app otherwise defaults to the top model at high effort, which
    # ran through most of a weekly limit in one onboarding.
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("create"); p.add_argument("--parent", required=True); p.add_argument("--name", default="workspace")
    p.add_argument("--seed"); p.add_argument("--user-name")
    p.add_argument("--no-github", action="store_true", help="local repos only (tests)")
    p = sub.add_parser("move-code"); p.add_argument("--seed", required=True)
    sub.add_parser("user-settings")
    p = sub.add_parser("git-identity"); p.add_argument("--name", required=True)
    args = parser.parse_args()
    handler = {"create": create, "move-code": move_code, "user-settings": user_settings, "git-identity": git_identity}[args.cmd]
    try:
        result = handler(args)
    except RuntimeError as exc:
        print(json.dumps({"error": str(exc)}))
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
