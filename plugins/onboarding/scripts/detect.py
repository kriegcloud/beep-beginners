# /// script
# requires-python = ">=3.11,<3.15"
# dependencies = ["pyyaml>=6"]
# ///
"""Everything a machine can tell onboarding about itself, as JSON.

OS, edition and version, WSL, OneDrive folder redirection, tools and their
versions (from tools.yaml), git identity, SSH keys (file names only), GitHub
CLI sign-in, password managers, user name and the usual folders. Nothing here
reads a secret: SSH keys are listed by file name, sign-ins by yes or no.
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from state import load_state, save_state  # noqa: E402
from tools import detect_all  # noqa: E402

WINDOWS = os.name == "nt"


def sh(argv: list[str], timeout: float = 20) -> str:
    try:
        out = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False,
                             encoding="utf-8", errors="replace")
        return out.stdout.strip() if out.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def ps(script: str) -> str:
    return sh(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script], timeout=60)


def windows_facts() -> dict:
    raw = ps(r"""
$os = Get-CimInstance Win32_OperatingSystem
$shell = Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders'
$od = Get-ItemProperty 'HKCU:\Software\Microsoft\OneDrive\Accounts\Personal' -ErrorAction SilentlyContinue
$wsl = (wsl.exe --status 2>$null) -join ' '
$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
$inAdmins = [bool](Get-LocalGroupMember -Group Administrators -ErrorAction SilentlyContinue | Where-Object { $_.Name -like "*\$env:USERNAME" })
[pscustomobject]@{
  edition = $os.Caption; version = $os.Version; build = $os.BuildNumber
  user = $env:USERNAME; home = $env:USERPROFILE
  documents = [Environment]::ExpandEnvironmentVariables($shell.Personal)
  desktop = [Environment]::ExpandEnvironmentVariables($shell.Desktop)
  pictures = [Environment]::ExpandEnvironmentVariables($shell.'My Pictures')
  onedrive_folder = $env:OneDrive
  onedrive_signed_in = [bool]($od -and $od.UserEmail)
  wsl_installed = [bool](Get-Command wsl.exe -ErrorAction SilentlyContinue) -and ($wsl -notmatch 'not installed')
  running_elevated = $admin
  user_is_admin = $inAdmins
  bitwarden_extension = [bool](Get-ChildItem "$env:LOCALAPPDATA\Google\Chrome\User Data\*\Extensions\nngceckbapebfimnlniiiahkandclblb" -ErrorAction SilentlyContinue)
  bitwarden_desktop = [bool](Get-AppxPackage *Bitwarden* -ErrorAction SilentlyContinue) -or (Test-Path "$env:LOCALAPPDATA\Programs\Bitwarden")
  claude_in_chrome = [bool](Get-ChildItem "$env:LOCALAPPDATA\Google\Chrome\User Data\*\Extensions\fcoeoabgfenejglbffodgkkbkcdhcgfn" -ErrorAction SilentlyContinue)
} | ConvertTo-Json -Compress
""")
    facts = json.loads(raw) if raw else {"error": "PowerShell probe failed"}
    docs = str(facts.get("documents") or "")
    od = str(facts.get("onedrive_folder") or "")
    facts["documents_in_onedrive"] = bool(od) and docs.lower().startswith(od.lower())
    return facts


def posix_facts() -> dict:
    home = Path.home()
    return {
        "edition": platform.platform(), "version": platform.release(),
        "user": os.environ.get("USER", ""), "home": str(home),
        "documents": str(home / "Documents"),
        "onedrive_folder": "", "documents_in_onedrive": False,
        "bitwarden_desktop": bool(sh(["which", "bitwarden"])),
    }


def detect() -> dict:
    facts: dict = {"os": "windows" if WINDOWS else ("macos" if sys.platform == "darwin" else "linux")}
    facts.update(windows_facts() if WINDOWS else posix_facts())
    ssh_dir = Path.home() / ".ssh"
    facts["ssh_public_keys"] = sorted(p.name for p in ssh_dir.glob("*.pub")) if ssh_dir.exists() else []
    facts["git_identity"] = {"name": bool(sh(["git", "config", "--global", "user.name"])),
                             "email": bool(sh(["git", "config", "--global", "user.email"]))}
    gh_login = sh(["gh", "api", "user", "--jq", ".login"])
    facts["gh_signed_in"] = bool(gh_login)
    facts["gh_login"] = gh_login
    facts["password_managers"] = {
        "1password": bool(sh(["op", "--version"])) or facts.get("onepassword_app", False),
        "bitwarden": bool(facts.get("bitwarden_extension") or facts.get("bitwarden_desktop")),
    }
    facts["tools"] = detect_all(load_state().get("answers", {}))
    facts["tools_present"] = sorted(t for t, v in facts["tools"].items() if v.get("present"))
    facts["tools_missing"] = sorted(t for t, v in facts["tools"].items() if v.get("present") is False)
    default_ws = Path(facts.get("home") or Path.home()) / "Workspace"
    facts["default_workspace"] = str(default_ws)
    return facts


def main() -> int:
    facts = detect()
    state = load_state()
    state["facts"] = facts
    save_state(state)
    print(json.dumps(facts, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
