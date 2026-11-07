# /// script
# requires-python = ">=3.11,<3.15"
# dependencies = ["pyyaml>=6"]
# ///
"""Detect, install and verify the tools in tools.yaml (decision 11).

  tools.py detect                         which tools are present (JSON)
  tools.py plan                           what onboarding will install, split by scope
  tools.py install-user [--only ID ...]   user-scope installs, no UAC
  tools.py write-batch [--keys-url URL]   write the elevated batch .ps1 (Windows)
  tools.py run-batch                      run that batch: one UAC prompt, waits
  tools.py verify [--evidence FILE]       check every tool by using it

Answers that change the plan (AI subscriptions, extra requests) are read from
the onboarding state file (state.py). Results are printed as JSON and kept in
the state folder. Verify output never includes account details: tools that
need a sign-in report only whether the check matched.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
MANIFEST = HERE.parent / "tools.yaml"
sys.path.insert(0, str(HERE))
from state import load_state, save_state, state_dir  # noqa: E402

WINDOWS = os.name == "nt"
# Installers are console programs. Without this, each one opens its own
# console window in front of the user (rustup did, on the test VM, 2026-11-07).
NO_WINDOW = {"creationflags": subprocess.CREATE_NO_WINDOW} if WINDOWS else {}
OS_KEY = "windows" if WINDOWS else ("macos" if sys.platform == "darwin" else "linux")
WINGET_FLAGS = ["-e", "--source", "winget", "--accept-package-agreements",
                "--accept-source-agreements", "--disable-interactivity"]


# ------------------------------------------------------------------ manifest

def load_manifest() -> dict:
    return yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))


def wanted(tool: dict, answers: dict) -> bool:
    when = str(tool.get("when", "always"))
    subs = {s.lower() for s in answers.get("subscriptions", [])}
    if when == "always":
        return True
    if when == "request":
        return tool["id"] in answers.get("requests", [])
    if when == "subscription:any":
        return bool(subs - {"claude"})
    if when.startswith("subscription:"):
        return when.split(":", 1)[1] in subs
    return False


def for_os(value, default=None):
    """Pick the entry for this OS from a string or an OS-keyed map."""
    if value is None:
        return default
    if isinstance(value, dict):
        return value.get(OS_KEY, value.get("default", default))
    return value


def ordered(tools: list[dict]) -> list[dict]:
    by_id = {t["id"]: t for t in tools}
    seen: list[str] = []

    def visit(tid: str) -> None:
        if tid in seen or tid not in by_id:
            return
        for dep in by_id[tid].get("needs", []):
            visit(dep)
        seen.append(tid)

    for t in tools:
        visit(t["id"])
    return [by_id[t] for t in seen]


# ------------------------------------------------------------------ running

def refresh_path() -> None:
    """New installs change PATH in the registry, not in this process."""
    extra = [Path.home() / ".local" / "bin", Path.home() / ".cargo" / "bin",
             Path.home() / ".bun" / "bin"]
    if WINDOWS:
        import winreg
        parts: list[str] = []
        for hive, key in ((winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
                          (winreg.HKEY_CURRENT_USER, "Environment")):
            try:
                with winreg.OpenKey(hive, key) as k:
                    parts.append(os.path.expandvars(winreg.QueryValueEx(k, "Path")[0]))
            except OSError:
                continue
        local = Path(os.environ.get("LOCALAPPDATA", ""))
        extra += [local / "Microsoft" / "WinGet" / "Links", local / "Microsoft" / "WindowsApps",
                  local / "Programs" / "Microsoft VS Code" / "bin"]
        os.environ["PATH"] = os.pathsep.join([*parts, *map(str, extra), os.environ.get("PATH", "")])
    else:
        os.environ["PATH"] = os.pathsep.join([*map(str, extra), "/opt/homebrew/bin", os.environ.get("PATH", "")])


def run(command: str, timeout: float = 600) -> subprocess.CompletedProcess[str]:
    tmp = tempfile.mkdtemp(prefix="beep-check-").replace("\\", "/")
    command = command.replace("{tmp}", tmp)
    argv = (["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", command]
            if WINDOWS else ["sh", "-c", command])
    try:
        return subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False, **NO_WINDOW,
                              encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(argv, 124, "", f"timed out after {timeout:.0f}s")
    except FileNotFoundError as exc:
        return subprocess.CompletedProcess(argv, 127, "", str(exc))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def first_line(text: str) -> str:
    for line in text.splitlines():
        if line.strip():
            return line.strip()[:160]
    return ""


# ------------------------------------------------------------------ detect / plan

def detect_one(tool: dict) -> dict:
    cmd = for_os(tool.get("check", {}).get("detect"))
    if cmd is None:
        return {"present": None, "note": "no detect command for this OS"}
    out = run(cmd, timeout=60)
    return {"present": out.returncode == 0, "version": first_line(out.stdout) if out.returncode == 0 else ""}


def detect_batch_windows(tools: list[dict]) -> dict:
    """One PowerShell process for every detect check. Starting PowerShell
    costs seconds on a fresh Windows machine, so one per tool is too slow."""
    blocks = []
    for tool in tools:
        cmd = for_os(tool.get("check", {}).get("detect"))
        if cmd is None:
            continue
        body = cmd.replace("{tmp}", tempfile.gettempdir().replace("\\", "/"))
        # `exit` would end the shared process; inside the batch it must throw.
        body = re.sub(r"\bexit\s+1\b", "throw 'missing'", body)
        blocks.append(
            f"$global:LASTEXITCODE = 0; $ok = $true; $out = ''\n"
            f"try {{ $out = (& {{ {body} }} 2>$null | Out-String); if ($LASTEXITCODE -ne 0) {{ $ok = $false }} }} "
            f"catch {{ $ok = $false }}\n"
            f"if (-not $?) {{ $ok = $false }}\n"
            f"[pscustomobject]@{{ id = '{tool['id']}'; present = $ok; version = (($out -split \"`n\") | ? {{ $_.Trim() }} | Select -First 1) }} | ConvertTo-Json -Compress\n")
    script = "$ErrorActionPreference = 'Stop'\n" + "".join(blocks)
    out = run(script, timeout=300)
    found = {}
    for line in out.stdout.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            found[row["id"]] = {"present": bool(row["present"]),
                                "version": (row.get("version") or "").strip()[:160] if row["present"] else ""}
    return found


def detect_all(answers: dict) -> dict:
    refresh_path()
    manifest = load_manifest()
    tools = [t for t in manifest["tools"] if wanted(t, answers)]
    batch = detect_batch_windows(tools) if WINDOWS else {}
    result = {}
    for tool in tools:
        row = batch.get(tool["id"]) if WINDOWS else None
        result[tool["id"]] = {"name": tool["name"], **(row if row is not None else detect_one(tool))}
    return result


def plan(answers: dict) -> dict:
    manifest = load_manifest()
    found = detect_all(answers)
    user, machine, present, unsupported = [], [], [], []
    for tool in ordered(manifest["tools"]):
        if tool["id"] not in found:
            continue
        if found[tool["id"]]["present"]:
            present.append(tool["id"])
            continue
        route = tool.get(OS_KEY)
        if not route:
            unsupported.append(tool["id"])
        elif route.get("scope") == "machine":
            machine.append(tool["id"])
        else:
            user.append(tool["id"])
    return {"os": OS_KEY, "present": present, "install_user": user, "install_machine": machine,
            "unsupported": unsupported,
            "why": {t["id"]: t["why"] for t in manifest["tools"] if t["id"] in user + machine}}


# ------------------------------------------------------------------ installs

def winget_install(winget_id: str, route: dict) -> tuple[bool, str]:
    args = ["winget", "install", "--id", winget_id, *WINGET_FLAGS]
    if route.get("scope"):
        args += ["--scope", route["scope"]]
    if route.get("scope") == "user":
        # Dependencies such as the Visual C++ runtime install machine-wide and
        # would show an admin prompt. The elevated batch installs them instead.
        args += ["--skip-dependencies"]
    if route.get("installer_type"):
        args += ["--installer-type", route["installer_type"]]
    if route.get("override"):
        args += ["--override", route["override"]]
    out = subprocess.run(args, capture_output=True, text=True, check=False, **NO_WINDOW, encoding="utf-8", errors="replace")
    code = out.returncode & 0xFFFFFFFF
    if code == 0x8A150010 and route.get("scope") == "user":
        # "No applicable installer": the package declares no scope (rustup is
        # one). It installs per user anyway, so try again without --scope.
        args = [a for a in args if a not in ("--scope", "user")]
        out = subprocess.run(args, capture_output=True, text=True, check=False, **NO_WINDOW, encoding="utf-8", errors="replace")
        code = out.returncode & 0xFFFFFFFF
    ok = code in {c & 0xFFFFFFFF for c in load_manifest()["winget_success_codes"]}
    return ok, f"winget {winget_id} exit 0x{code:08X}"


def github_release_install(spec: str) -> tuple[bool, str]:
    _, repo, asset = spec.split(":", 2)
    with urllib.request.urlopen(f"https://api.github.com/repos/{repo}/releases/latest", timeout=60) as r:
        release = json.load(r)
    match = next((a for a in release.get("assets", []) if a["name"] == asset), None)
    if not match:
        return False, f"{asset} not found in {repo} {release.get('tag_name')}"
    target = Path(tempfile.gettempdir()) / asset
    urllib.request.urlretrieve(match["browser_download_url"], target)
    out = subprocess.run([str(target), "/S"], capture_output=True, text=True, check=False, **NO_WINDOW, timeout=900)
    return out.returncode == 0, f"{asset} {release.get('tag_name')} exit {out.returncode}"


def register_logon_task(name: str) -> tuple[bool, str]:
    script = (f"$exe = (Get-Command cli-proxy-api -ErrorAction Stop).Source; "
              f"$a = New-ScheduledTaskAction -Execute $exe; "
              f"$t = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME; "
              f"$s = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit 0; "
              f"Register-ScheduledTask -TaskName 'beep-beginners-{name}' -Action $a -Trigger $t -Settings $s -Force | Out-Null; "
              f"Start-ScheduledTask -TaskName 'beep-beginners-{name}'")
    out = run(script, timeout=60)
    return out.returncode == 0, f"logon task beep-beginners-{name}: {first_line(out.stderr) or 'registered'}"


def install_tool(tool: dict) -> dict:
    route = tool.get(OS_KEY) or {}
    log: list[str] = []
    ok = True
    try:
        if route.get("winget") and WINDOWS:
            ok, msg = winget_install(route["winget"], route)
            log.append(msg)
            for extra in route.get("also", []):
                ok2, msg2 = winget_install(extra, {"scope": route.get("scope")})
                log.append(msg2)
                ok = ok and ok2
        elif route.get("brew") and not WINDOWS:
            name = str(route["brew"])
            cask = name.startswith("cask:")
            out = run(f"brew install {'--cask ' if cask else ''}{name.removeprefix('cask:')}", timeout=1800)
            ok, msg = out.returncode == 0, f"brew {name} exit {out.returncode}"
            log.append(msg)
        elif route.get("apt") and not WINDOWS:
            out = run(f"sudo apt-get install -y {route['apt']}", timeout=1800)
            ok = out.returncode == 0
            log.append(f"apt {route['apt']} exit {out.returncode}")
        elif route.get("script", "").startswith("github-release:"):
            ok, msg = github_release_install(route["script"])
            log.append(msg)
        elif route.get("script", "").startswith("elevated:"):
            return {"id": tool["id"], "ok": False, "log": ["runs in the elevated batch"]}
        elif route.get("script"):
            out = run(route["script"], timeout=1800)
            ok = out.returncode == 0
            log.append(f"script exit {out.returncode} {first_line(out.stderr)}")
        else:
            return {"id": tool["id"], "ok": False, "log": [f"no install route for {OS_KEY}"]}
        refresh_path()
        post = route.get("post")
        if ok and post:
            if post.startswith("logon-task:"):
                ok, msg = register_logon_task(post.split(":", 1)[1])
            else:
                out = run(post, timeout=1800)
                ok, msg = out.returncode == 0, f"post exit {out.returncode} {first_line(out.stderr)}"
            log.append(msg)
    except Exception as exc:  # noqa: BLE001 - report every failure, never crash onboarding
        ok = False
        log.append(f"{exc.__class__.__name__}: {exc}")
    return {"id": tool["id"], "ok": ok, "log": log}


def install_user(answers: dict, only: list[str] | None) -> dict:
    p = plan(answers)
    targets = [t for t in p["install_user"] if not only or t in only]
    manifest = {t["id"]: t for t in load_manifest()["tools"]}
    results = [install_tool(manifest[t]) for t in targets]
    return {"installed": results, "detect_after": detect_all(answers)}


# ------------------------------------------------------------------ elevated batch

OPENSSH_BLOCK = r"""
# OpenSSH Server, reachable only over Tailscale, only with the helper's keys (decision 22).
Step 'OpenSSH Server' {
  if ((Get-WindowsCapability -Online -Name OpenSSH.Server*).State -ne 'Installed') {
    Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0 | Out-Null
  }
  $keys = 'C:\ProgramData\ssh\administrators_authorized_keys'
  # Wrap every list in @() at the point of use: PowerShell unwraps a one-item
  # array into a plain string, and string + array concatenates into one line.
  $new = @(@(@KEYS@) | Where-Object { $_ -match '^(ssh-|ecdsa-|sk-)' })
  if ($new.Count -gt 0) {
    $have = @(if (Test-Path $keys) { Get-Content $keys })
    $all = @(@($have) + @($new) | Where-Object { $_ -match '^(ssh-|ecdsa-|sk-)' } | Select-Object -Unique)
    Set-Content -Path $keys -Value $all -Encoding ascii
    icacls $keys /inheritance:r /grant 'Administrators:F' /grant 'SYSTEM:F' | Out-Null
  }
  # Password logins off for everyone. The line must sit above the first Match
  # block: Windows' default sshd_config ends with "Match Group administrators",
  # and anything appended after it would apply only inside that block.
  $cfg = 'C:\ProgramData\ssh\sshd_config'
  if (Test-Path $cfg) {
    $lines = @(Get-Content $cfg | Where-Object { $_ -notmatch '^\s*PasswordAuthentication\s' })
    $at = [Array]::FindIndex([string[]]$lines, [Predicate[string]]{ param($l) $l -match '^\s*Match\s' })
    if ($at -lt 0) { $lines += 'PasswordAuthentication no' }
    else { $lines = @($lines[0..($at - 1)]) + 'PasswordAuthentication no' + '' + @($lines[$at..($lines.Count - 1)]) }
    Set-Content -Path $cfg -Value $lines -Encoding ascii
  }
  Set-Service sshd -StartupType Automatic
  Start-Service sshd
  # Close the default rule that opens port 22 on every network.
  Get-NetFirewallRule -Name 'OpenSSH-Server-In-TCP' -ErrorAction SilentlyContinue | Disable-NetFirewallRule
  if (-not (Get-NetFirewallRule -Name 'beep-beginners-ssh-tailscale' -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -Name 'beep-beginners-ssh-tailscale' -DisplayName 'SSH from Tailscale only (beep-beginners)' `
      -Direction Inbound -Protocol TCP -LocalPort 22 -RemoteAddress 100.64.0.0/10 -Action Allow -Profile Any | Out-Null
  }
}
"""

BATCH_HEAD = r"""# beep-beginners elevated batch. Runs once, behind one UAC prompt.
$ErrorActionPreference = 'Continue'
$results = [ordered]@{}
function Step($name, [scriptblock]$body) {
  try { & $body; $results[$name] = 'ok' } catch { $results[$name] = "failed: $($_.Exception.Message)" }
}
$wingetFlags = @('-e','--source','winget','--accept-package-agreements','--accept-source-agreements','--disable-interactivity')
"""

BATCH_TAIL = r"""
$results | ConvertTo-Json | Set-Content -Path '@RESULT@' -Encoding utf8
"""


def ps_quote(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"


def write_batch(answers: dict, keys_url: str | None, keep_ssh_rule: bool = False) -> dict:
    if not WINDOWS:
        return {"error": "the elevated batch is Windows only; macOS and Linux use sudo per install"}
    p = plan(answers)
    manifest = {t["id"]: t for t in load_manifest()["tools"]}
    keys: list[str] = []
    if keys_url:
        with urllib.request.urlopen(keys_url, timeout=30) as r:
            keys = [k.strip() for k in r.read().decode().splitlines() if k.strip()]
    body = [BATCH_HEAD]
    for tid in p["install_machine"]:
        route = manifest[tid]["windows"]
        if route.get("script") == "elevated:openssh":
            continue
        extra = f", '--override', {ps_quote(route['override'])}" if route.get("override") else ""
        body.append(f"Step {ps_quote(manifest[tid]['name'])} {{ & winget install --id {route['winget']} @wingetFlags --scope machine{extra} | Out-Null; "
                    f"if ($LASTEXITCODE -notin @(0, -1978335189, -1978335135, -1978334963)) {{ throw \"winget exit $LASTEXITCODE\" }} }}")
    # OpenSSH is (re)configured whenever helper keys are given, even if the
    # capability is already installed (the test VM's harness has it on).
    if "openssh-server" in p["install_machine"] or keys:
        body.append(OPENSSH_BLOCK.replace("@KEYS@", ", ".join(ps_quote(k) for k in keys) or "''"))
    folder = state_dir()
    result_file = folder / "elevated-result.json"
    body.append(BATCH_TAIL.replace("@RESULT@", str(result_file)))
    path = folder / "elevated-batch.ps1"
    path.write_text("\n".join(body), encoding="utf-8-sig")
    return {"batch": str(path), "result": str(result_file), "steps": p["install_machine"],
            "helper_keys": len(keys)}


def run_batch() -> dict:
    folder = state_dir()
    batch, result = folder / "elevated-batch.ps1", folder / "elevated-result.json"
    if not batch.exists():
        return {"error": "write the batch first"}
    result.unlink(missing_ok=True)
    launcher = (f"$p = Start-Process powershell.exe -Verb RunAs -Wait -PassThru "
                f"-ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File',{ps_quote(str(batch))}; exit $p.ExitCode")
    out = run(launcher, timeout=7200)
    refresh_path()
    if not result.exists():
        return {"ran": False, "note": "The permission prompt was declined or the batch didn't finish.",
                "stderr": first_line(out.stderr)}
    return {"ran": True, "steps": json.loads(result.read_text(encoding="utf-8-sig"))}


# ------------------------------------------------------------------ verify

def verify(answers: dict) -> dict:
    refresh_path()
    rows = []
    for tool in ordered(load_manifest()["tools"]):
        if not wanted(tool, answers):
            continue
        check = tool.get("check", {})
        cmd = for_os(check.get("verify"))
        if cmd is None:
            rows.append({"id": tool["id"], "ok": None, "note": "no verify command for this OS"})
            continue
        out = run(cmd, timeout=900)
        expect = str(check.get("expect", "")).replace(
            "{agents_vault}", re.escape(os.environ.get("BEEP_BEGINNERS_AGENTS_VAULT", "Agents")))
        matched = bool(re.search(expect, out.stdout + out.stderr, re.M))
        row = {"id": tool["id"], "name": tool["name"], "ok": out.returncode == 0 and matched,
               "exit": out.returncode, "expect_matched": matched}
        if "signin" not in tool:
            row["output"] = first_line(out.stdout)
        elif not row["ok"]:
            row["needs_signin"] = tool["signin"]
        rows.append(row)
    summary = {"os": OS_KEY, "machine": platform.platform(), "all_ok": all(r["ok"] for r in rows if r["ok"] is not None),
               "tools": rows}
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("detect")
    sub.add_parser("plan")
    p = sub.add_parser("install-user"); p.add_argument("--only", nargs="*")
    p = sub.add_parser("write-batch"); p.add_argument("--keys-url")
    sub.add_parser("run-batch")
    p = sub.add_parser("verify"); p.add_argument("--evidence", type=Path)
    args = parser.parse_args()

    state = load_state()
    answers = state.get("answers", {})
    if args.cmd == "detect":
        result = detect_all(answers)
    elif args.cmd == "plan":
        result = plan(answers)
    elif args.cmd == "install-user":
        result = install_user(answers, args.only)
    elif args.cmd == "write-batch":
        result = write_batch(answers, args.keys_url)
    elif args.cmd == "run-batch":
        result = run_batch()
    else:
        result = verify(answers)
        if args.evidence:
            args.evidence.write_text(json.dumps(result, indent=2), encoding="utf-8")
    state.setdefault("tools", {})[args.cmd] = result
    save_state(state)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
