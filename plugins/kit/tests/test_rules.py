# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest>=8"]
# ///
"""Run: uv run --script plugins/kit/tests/test_rules.py"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hooks"))
from rules import check_delete, check_gh, check_git, check_tool, is_secret_path  # noqa: E402

BLOCK_GIT = [
    "git reset --hard",
    "git reset --hard HEAD~1",
    "git -C C:/ws reset --hard",
    "git clean -fd",
    "git clean -xfd",
    "git clean --force",
    "git branch -D old",
    "git branch --delete --force old",
    "git checkout .",
    "git checkout -- .",
    "git restore .",
    "git push --force",
    "git push -f origin main",
    "git push --force-with-lease",
    "git push origin +main",
    "git push origin :main",
    "git push --delete origin main",
    "git push upstream main",
    "git push https://github.com/x/y.git main",
    "git status && git push -f",
    'bash -c "git reset --hard"',
    'powershell -Command "git push --force"',
    "cd C:\\ws; git clean -f",
    "git add -A",
    "git add .",
    "git commit -m 'Add listing for Pikachu'",
    "git commit -am x",
    "git merge goal/x",
    "git -C C:/ws commit -m x",
]
ALLOW_GIT = [
    "git push",
    "git push origin",
    "git push origin main",
    "git push -u origin HEAD",
    "git status",
    "git reset HEAD file.txt",
    "git reset --soft HEAD~1",
    "git clean -n",
    "git branch -d merged",
    "git checkout main",
    "git checkout -b new-branch",
    "git restore file.txt",
    "git log --oneline -5",
]


@pytest.mark.parametrize("cmd", BLOCK_GIT)
def test_git_blocked(cmd: str) -> None:
    assert check_git(cmd), cmd


@pytest.mark.parametrize("cmd", ALLOW_GIT)
def test_git_allowed(cmd: str) -> None:
    assert check_git(cmd) is None, cmd


WIN = "C:\\Users\\ed\\Workspace\\ed-workspace"
POSIX = "/home/ed/Workspace/ed-workspace"


@pytest.mark.parametrize("cmd,cwd,proj", [
    ("rm -rf /", POSIX, POSIX),
    ("rm -rf ~", POSIX, POSIX),
    ("rm -rf ../other", POSIX, POSIX),
    ("rm -rf /home/ed/Documents", POSIX, POSIX),
    (f"rm -rf {POSIX}", POSIX, POSIX),
    ("Remove-Item -Recurse -Force C:\\Users\\ed\\Documents", WIN, WIN),
    ("Remove-Item -Path ..\\PokeLedger -Recurse", WIN, WIN),
    ("del /s /q C:\\Windows\\Temp2", WIN, WIN),
    ("rd /s /q D:\\", WIN, WIN),
    ("Remove-Item $HOME\\Desktop\\x.txt", WIN, WIN),
])
def test_delete_blocked(cmd: str, cwd: str, proj: str) -> None:
    assert check_delete(cmd, cwd, proj), cmd


@pytest.mark.parametrize("cmd,cwd,proj", [
    ("rm -rf build", POSIX, POSIX),
    ("rm notes/old.md", POSIX, POSIX),
    (f"rm -rf {POSIX}/tmp", POSIX, POSIX),
    ("Remove-Item -Recurse .\\build", WIN, WIN),
    ("Remove-Item -Path drafts\\old.md", WIN, WIN),
    ("del /q drafts\\old.md", WIN, WIN),
    ("git rm old.md", POSIX, POSIX),
])
def test_delete_allowed(cmd: str, cwd: str, proj: str) -> None:
    assert check_delete(cmd, cwd, proj) is None, cmd


@pytest.mark.parametrize("path", [
    ".env", "app/.env", ".env.local", "C:\\Users\\ed\\.ssh\\id_ed25519", "~/.ssh/config",
    "server.pem", "cert.pfx", "secrets/api.txt", "secrets.json", "bitwarden_export_2026.json",
    "C:\\Users\\ed\\.cli-proxy-api\\config.yaml", ".git-credentials", "vault.1pux",
])
def test_secret_paths(path: str) -> None:
    assert is_secret_path(path), path


@pytest.mark.parametrize("path", [
    ".env.example", "README.md", "id_ed25519.pub", "PokeSeller/config.json", "docs/secrets-policy.md",
    "listing-rules.yaml", "environment.md",
])
def test_not_secret_paths(path: str) -> None:
    assert not is_secret_path(path), path


def test_tool_routing() -> None:
    assert check_tool("Read", {"file_path": "C:\\ws\\.env"}, WIN, WIN)
    assert check_tool("Read", {"file_path": "C:\\ws\\README.md"}, WIN, WIN) is None
    assert check_tool("PowerShell", {"command": "Get-Content .env"}, WIN, WIN)
    assert check_tool("Bash", {"command": "cat ~/.ssh/id_rsa"}, POSIX, POSIX)
    assert check_tool("Grep", {"pattern": "token", "path": "secrets/"}, POSIX, POSIX)
    assert check_tool("PowerShell", {"command": "git push --force"}, WIN, WIN)
    assert check_tool("WebFetch", {"url": "https://example.com/.env"}, WIN, WIN) is None


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))


BLOCK_GH = [
    "gh pr merge 12",
    "gh pr merge --squash 12",
    "gh api -X PUT repos/o/r/pulls/12/merge",
    "gh api --method PUT /repos/o/r/pulls/12/merge -f merge_method=squash",
    "gh api -X POST repos/o/r/merges -f base=main -f head=goal/x",
    "gh api -X DELETE repos/o/r/git/refs/heads/goal/x",
    "gh api -X PUT repos/o/r/branches/main/protection",
    'powershell -Command "gh pr merge 3"',
]
ALLOW_GH = [
    "gh api repos/o/r/pulls",
    "gh api repos/o/r/pulls/12",
    "gh api repos/o/r/commits/abc/check-runs",
    "gh api -X POST repos/o/r/pulls -f title=x -f head=goal/x -f base=main",
    "gh api repos/o/r/branches/main/protection",
    "gh auth status",
    "gh api user --jq .login",
    "uv run --script kit.py pr merge 12",
]


@pytest.mark.parametrize("cmd", BLOCK_GH)
def test_gh_blocked(cmd: str) -> None:
    assert check_gh(cmd), cmd


@pytest.mark.parametrize("cmd", ALLOW_GH)
def test_gh_allowed(cmd: str) -> None:
    assert check_gh(cmd) is None and check_git(cmd) is None, cmd
