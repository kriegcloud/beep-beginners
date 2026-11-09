"""Shared helpers: git and shell calls with timeouts, paths, dates, slugs.

Standard library only. Every subprocess call has a timeout and never prompts,
so a network hiccup can't wedge a session or a caretaker run.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import subprocess
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parents[2]  # plugins/kit
TEMPLATES = KIT_ROOT / "templates"
WORKSPACE_TEMPLATE = KIT_ROOT / "template"

GIT_ENV = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "never",
           "GIT_OPTIONAL_LOCKS": "0"}


class KitError(Exception):
    """A failure the caller should see as a plain sentence, not a traceback."""


def today() -> str:
    return dt.date.today().isoformat()


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug[:60].rstrip("-") or "untitled"


def run(argv: list[str], cwd: Path | None = None, timeout: float = 60, env: dict | None = None,
        input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=timeout,
                              env=env or GIT_ENV, check=False, encoding="utf-8", errors="replace",
                              input=input_text)
    except FileNotFoundError:
        return subprocess.CompletedProcess(argv, 127, "", f"{argv[0]} is not installed")
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(argv, 124, "", f"{argv[0]} timed out after {timeout}s")


def git(root: Path, *args: str, timeout: float = 30, env: dict | None = None,
        check: bool = False) -> subprocess.CompletedProcess[str]:
    out = run(["git", "-C", str(root), *args], timeout=timeout, env=env)
    if check and out.returncode != 0:
        raise KitError(f"git {' '.join(args[:2])} failed: {(out.stderr or out.stdout).strip()[-300:]}")
    return out


def repo_root(start: Path) -> Path | None:
    out = git(start, "rev-parse", "--show-toplevel", timeout=10)
    return Path(out.stdout.strip()) if out.returncode == 0 and out.stdout.strip() else None


def require_root(start: Path) -> Path:
    root = repo_root(start)
    if root is None:
        raise KitError(f"{start} is not inside a git repository")
    return root


def git_dir(root: Path) -> Path:
    out = git(root, "rev-parse", "--git-dir", timeout=10)
    path = Path(out.stdout.strip() or ".git")
    return path if path.is_absolute() else root / path


def kit_state_dir(root: Path) -> Path:
    """Local-only state lives under .git/kit so it never enters the tree."""
    folder = git_dir(root) / "kit"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def fill(text: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value)
    return text


def fill_tree(folder: Path, values: dict[str, str]) -> None:
    for path in folder.rglob("*"):
        if path.is_file() and path.suffix in (".md", ".toml", ".json", ".yml", ".yaml", ".py", ".ts", ".txt"):
            path.write_text(fill(path.read_text(encoding="utf-8"), values), encoding="utf-8")


def plain_days_ago(date_text: str) -> int | None:
    try:
        return (dt.date.today() - dt.date.fromisoformat(date_text[:10])).days
    except ValueError:
        return None
