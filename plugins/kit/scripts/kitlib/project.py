"""projects/<name> (D43, D56): one folder per app or automation, from the
Python or TypeScript template, with its own CI workflow (path-filtered) and
its own Dependabot entry.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from .common import TEMPLATES, KitError, fill_tree, read_json, slugify, today, write_json

STACKS = {"python": "project-python", "ts": "project-ts"}
WORKFLOWS = Path(".github") / "workflows"
DEPENDABOT = Path(".github") / "dependabot.yml"

_ECOSYSTEM = {"python": "uv", "ts": "bun"}


def _package_name(name: str) -> str:
    return re.sub(r"[^a-z0-9_]", "_", name.lower()).strip("_") or "project"


def new(root: Path, name: str, stack: str, goal: str | None, mode: str = "operator",
        summary: str = "", source: Path | None = None) -> dict:
    if stack not in STACKS:
        raise KitError("stack must be python or ts")
    slug = slugify(name)
    if slug != name:
        raise KitError(f"use a folder-safe name such as {slug}")
    target = root / "projects" / name
    if target.exists():
        raise KitError(f"projects/{name} already exists")
    shutil.copytree(TEMPLATES / STACKS[stack], target)
    values = {"name": name, "package": _package_name(name), "date": today(), "mode": mode,
              "summary": summary or f"The {name} project.", "goal": goal or "", "stack": stack,
              "goal_line": f"It belongs to the goal `goals/{goal}/`." if goal else "It isn't tied to a goal yet."}
    placeholder = target / "src" / "{{package}}"
    if placeholder.exists():
        placeholder.rename(target / "src" / values["package"])
    fill_tree(target, values)
    (target / "WORKFLOW.yml.tmpl").unlink(missing_ok=True)
    write_json(target / ".kit.json", {"schema": "beep-beginners/project/v1", "name": name, "stack": stack,
                                       "goal": goal, "mode": mode, "created": today()})
    copied = []
    if source:
        copied = bring_in(source, target, stack)
    lock = _lockfile(target, stack)
    workflow = _write_workflow(root, name, stack)
    _add_dependabot(root, name, stack)
    if goal:
        packet = root / "goals" / goal / ".packet.json"
        state = read_json(packet, None)
        if state is not None:
            state.setdefault("projects", [])
            if name not in state["projects"]:
                state["projects"].append(name)
            write_json(packet, state)
    return {"project": f"projects/{name}", "stack": stack, "branch": f"goal/{goal}" if goal else f"project/{name}",
            "workflow": workflow, "copied": copied, "mode": mode, "lockfile": lock}


def _lockfile(target: Path, stack: str) -> str:
    """Write the lockfile Dependabot and CI read. Best effort: the tool may be
    missing on the machine, in which case CI resolves fresh."""
    from .common import run
    argv = ["uv", "lock"] if stack == "python" else ["bun", "install", "--silent"]
    out = run(argv, cwd=target, timeout=180)
    name = "uv.lock" if stack == "python" else "bun.lock"
    if out.returncode == 0 and (target / name).exists():
        return name
    detail = ((out.stderr or out.stdout).strip().splitlines() or ["tool missing"])[-1][:80]
    return f"none ({detail})"


def bring_in(source: Path, target: Path, stack: str) -> list[str]:
    """Copy code (never data) from a Documents folder into the project."""
    patterns = {"python": ("*.py", "*.sql", "*.ipynb", "*.toml", "*.md"), "ts": ("*.ts", "*.tsx", "*.js", "*.json", "*.md")}[stack]
    copied = []
    if not source.exists():
        raise KitError(f"{source} doesn't exist")
    for pattern in patterns:
        for f in source.rglob(pattern):
            if any(part in (".git", "node_modules", ".venv", "__pycache__") for part in f.parts):
                continue
            rel = f.relative_to(source)
            dest = target / ("src" if stack == "python" and f.suffix == ".py" else ".") / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dest)
            copied.append(str(rel).replace("\\", "/"))
    return copied


def _write_workflow(root: Path, name: str, stack: str) -> str:
    template = (TEMPLATES / STACKS[stack] / "WORKFLOW.yml.tmpl").read_text(encoding="utf-8")
    text = template.replace("{{name}}", name)
    (root / WORKFLOWS).mkdir(parents=True, exist_ok=True)
    out = root / WORKFLOWS / f"project-{name}.yml"
    out.write_text(text, encoding="utf-8")
    # The template file itself must not travel into the project.
    tmpl = root / "projects" / name / "WORKFLOW.yml.tmpl"
    if tmpl.exists():
        tmpl.unlink()
    return str(out.relative_to(root)).replace("\\", "/")


def _add_dependabot(root: Path, name: str, stack: str) -> None:
    path = root / DEPENDABOT
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('version: 2\nupdates:\n  - package-ecosystem: "github-actions"\n    directory: "/"\n'
                        '    schedule:\n      interval: "weekly"\n    cooldown:\n      default-days: 7\n', encoding="utf-8")
    text = path.read_text(encoding="utf-8")
    directory = f"/projects/{name}"
    if f'directory: "{directory}"' in text:
        return
    # A seven-day cooldown on new versions (semgrep's dependabot-missing-cooldown rule, D50).
    entry = (f'  - package-ecosystem: "{_ECOSYSTEM[stack]}"\n    directory: "{directory}"\n'
             f'    schedule:\n      interval: "daily"\n    cooldown:\n      default-days: 7\n')
    path.write_text(text.rstrip("\n") + "\n" + entry, encoding="utf-8")


def list_projects(root: Path) -> list[dict]:
    base = root / "projects"
    found = []
    for meta in sorted(base.glob("*/.kit.json")) if base.exists() else []:
        data = read_json(meta, {})
        if data:
            found.append(data)
    return found
