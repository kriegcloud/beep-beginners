# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Turn the helper's remote access on or off, or report its state (decision 22).

  remote_access.py status    JSON: sshd, firewall rule, Tailscale, key count
  remote_access.py off       stop sshd, disable it and the firewall rule (one UAC prompt)
  remote_access.py on        enable and start sshd and the firewall rule (one UAC prompt)

Windows only. Onboarding sets everything up the first time. This script only
flips the switch. It never prints key material, only how many keys exist.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

RULE = "beep-beginners-ssh-tailscale"
KEYS = r"C:\ProgramData\ssh\administrators_authorized_keys"


def powershell(script: str, timeout: float = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                          capture_output=True, text=True, timeout=timeout, check=False)


def status() -> dict:
    script = f"""
$s = Get-Service sshd -ErrorAction SilentlyContinue
$r = Get-NetFirewallRule -Name '{RULE}' -ErrorAction SilentlyContinue
$k = if (Test-Path '{KEYS}') {{ @(Get-Content '{KEYS}' | Where-Object {{ $_ -match '^ssh-' }}).Count }} else {{ 0 }}
$ts = $null
$exe = Join-Path $env:ProgramFiles 'Tailscale\\tailscale.exe'
if (Test-Path $exe) {{ try {{ $ts = (& $exe status --json | ConvertFrom-Json).BackendState }} catch {{}} }}
[pscustomobject]@{{
  sshd_installed = [bool]$s
  sshd_running = [bool]($s -and $s.Status -eq 'Running')
  sshd_startup = if ($s) {{ "$($s.StartType)" }} else {{ $null }}
  firewall_rule_enabled = [bool]($r -and "$($r.Enabled)" -eq 'True')
  authorized_key_count = $k
  tailscale = $ts
}} | ConvertTo-Json -Compress
"""
    out = powershell(script)
    try:
        data = json.loads(out.stdout.strip() or "{}")
    except json.JSONDecodeError:
        data = {"error": out.stderr.strip()[-300:]}
    data["access_on"] = bool(data.get("sshd_running") and data.get("firewall_rule_enabled"))
    return data


def elevated(script: str) -> int:
    """Run a script in one elevated PowerShell. Windows shows one UAC prompt."""
    with tempfile.TemporaryDirectory() as tmp:
        ps1 = Path(tmp) / "remote-access.ps1"
        ps1.write_text("$ErrorActionPreference = 'Stop'\n" + script, encoding="utf-8")
        launcher = (f"$p = Start-Process powershell.exe -Verb RunAs -Wait -PassThru -WindowStyle Hidden "
                    f"-ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File','{ps1}'; exit $p.ExitCode")
        return powershell(launcher, timeout=300).returncode


def turn_off() -> int:
    return elevated(f"""
Stop-Service sshd -ErrorAction SilentlyContinue
Set-Service sshd -StartupType Disabled
Disable-NetFirewallRule -Name '{RULE}' -ErrorAction SilentlyContinue
""")


def turn_on() -> int:
    return elevated(f"""
Set-Service sshd -StartupType Automatic
Start-Service sshd
Enable-NetFirewallRule -Name '{RULE}'
""")


def main() -> int:
    if os.name != "nt":
        print(json.dumps({"error": "Remote access switching is only built for Windows."}))
        return 1
    action = sys.argv[1] if len(sys.argv) > 1 else "status"
    if action in ("on", "off"):
        code = (turn_on if action == "on" else turn_off)()
        result = status()
        result["elevated_exit_code"] = code
        print(json.dumps(result, indent=2))
        return 0 if result["access_on"] == (action == "on") else 1
    print(json.dumps(status(), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
