# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Ask where the workspace goes, with the system's own folder picker.

  pick_folder.py [--default PATH]

Prints JSON: {"path": ..., "source": "env|dialog|cancelled|no-dialog",
"onedrive": bool, "warning": ...}. BEEP_BEGINNERS_WORKSPACE skips the dialog
(automated runs). "no-dialog" means the agent should ask in chat instead.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

PS_DIALOG = r"""
Add-Type -AssemblyName System.Windows.Forms
$owner = New-Object System.Windows.Forms.Form -Property @{ TopMost = $true; ShowInTaskbar = $false }
$d = New-Object System.Windows.Forms.FolderBrowserDialog
$d.Description = 'Pick the folder for your workspace. The suggested one is fine.'
$d.ShowNewFolderButton = $true
$d.SelectedPath = $env:BEEP_DEFAULT
if ($d.PSObject.Properties.Name -contains 'InitialDirectory') { $d.InitialDirectory = $env:BEEP_DEFAULT }
if ($d.ShowDialog($owner) -eq 'OK') { $d.SelectedPath } else { '::cancelled::' }
"""


def onedrive_roots() -> list[str]:
    roots = [os.environ.get(k, "") for k in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial")]
    return [r for r in roots if r]


def in_onedrive(path: str) -> bool:
    p = path.replace("/", "\\").lower().rstrip("\\")
    return any(p == r.lower().rstrip("\\") or p.startswith(r.lower().rstrip("\\") + "\\") for r in onedrive_roots()) \
        or "\\onedrive" in p


def dialog(default: str) -> str | None:
    env = {**os.environ, "BEEP_DEFAULT": default}
    if os.name == "nt":
        Path(default).mkdir(parents=True, exist_ok=True)
        argv = ["powershell.exe", "-NoProfile", "-STA", "-Command", PS_DIALOG]
    elif sys.platform == "darwin":
        argv = ["osascript", "-e",
                f'POSIX path of (choose folder with prompt "Pick the folder for your workspace" default location POSIX file "{default}")']
    elif shutil.which("zenity"):
        argv = ["zenity", "--file-selection", "--directory", f"--filename={default}/"]
    elif shutil.which("kdialog"):
        argv = ["kdialog", "--getexistingdirectory", default]
    else:
        return None
    try:
        out = subprocess.run(argv, capture_output=True, text=True, env=env, timeout=1800, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    chosen = out.stdout.strip()
    if not chosen or chosen == "::cancelled::" or out.returncode not in (0,):
        return "::cancelled::" if out.returncode in (0, 1) else None
    return chosen.rstrip("/\\") or chosen


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--default", default=str(Path.home() / "Workspace"))
    args = parser.parse_args()
    if os.environ.get("BEEP_BEGINNERS_WORKSPACE"):
        path, source = os.environ["BEEP_BEGINNERS_WORKSPACE"], "env"
    else:
        chosen = dialog(args.default)
        if chosen is None:
            path, source = "", "no-dialog"
        elif chosen == "::cancelled::":
            path, source = "", "cancelled"
        else:
            path, source = chosen, "dialog"
    result = {"path": path, "source": source, "onedrive": bool(path) and in_onedrive(path)}
    if result["onedrive"]:
        result["warning"] = ("That folder syncs to OneDrive. OneDrive can damage git's history files, "
                             "so pick a folder outside OneDrive, like the suggested one.")
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
