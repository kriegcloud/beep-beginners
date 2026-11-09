#!/usr/bin/env bash
# Milkman proof runner for the Windows test VM. It wraps beep-effect's
# practice-gateway VM scripts (snapshot.sh, vm-run.sh, vm-type.sh) and never
# copies them.
#
#   run.sh baseline [snapshot]          winget inventory of a snapshot -> baseline/
#   run.sh prepare [snapshot]           revert, boot, copy the local kit in, start screenshots
#                                       (default: milkman-signed-in if saved, else claude-signed-in)
#   run.sh vm '<powershell>'            run a command over the harness SSH
#   run.sh vmi '<cmd.exe command>'      run a command in the desktop session
#   run.sh shot [name]                  screenshot (outside the repo) and print its path
#   run.sh click X Y                    click at screenshot coordinates (60% scale)
#   run.sh type 'text' | --key KEY...   type into the VM (beep-effect vm-type.sh)
#   run.sh evidence [out.md]            collect proof into evidence/ (no secret values)
#   run.sh evidence-import [src] [out]  import evidence.ps1 output the operator collected in their own session
#   run.sh reset                        delete the test repos, SSH key, Tailscale login
#   run.sh finish [--save milkman-NAME] stop, optionally save a milkman-* snapshot, revert clean
#
# Snapshots clean, claude-signed-in and agents-signed-in belong to the
# practice-gateway work. This script refuses to save them.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KIT="$(cd "$HERE/../.." && pwd)"
BEEP_EFFECT="${BEEP_EFFECT:-$HOME/YeeBois/projects/beep-effect}"
PG="$BEEP_EFFECT/goals/practice-gateway/ops/vm"
NAME="${VM_NAME:-practice-gateway-win11}"
STATE="${VM_STATE:-$HOME/VMs/practice-gateway}"
CONN="qemu:///session"
LOCK="$STATE/milkman.lock"
RUN="$PG/vm-run.sh"
# beep-effect's snapshot.sh and onboarding-proof.sh refuse to run while the
# Milkman lock exists, unless the caller says it holds the lock.
export BEEP_VM_LOCK_HOLDER=milkman
v() { virsh -c "$CONN" "$@"; }

for f in snapshot.sh vm-run.sh vm-type.sh; do
  [[ -x "$PG/$f" ]] || { echo "missing $PG/$f (set BEEP_EFFECT)" >&2; exit 1; }
done

# --------------------------------------------------------------- locking
# A Milkman run holds $LOCK from prepare (or baseline) until finish. Starting
# one is refused while the lock exists, while the VM is running for anyone
# else, or while a practice-gateway proof recorder is alive.
take_lock() {
  if [[ -f "$LOCK" ]]; then
    echo "a Milkman run is in progress ($(cat "$LOCK")); run 'run.sh finish' first" >&2; exit 1
  fi
  if [[ -f "$STATE/shots/recorder.pid" ]] && kill -0 "$(cat "$STATE/shots/recorder.pid")" 2>/dev/null; then
    echo "a practice-gateway proof is recording; wait for it to finish" >&2; exit 1
  fi
  if [[ "$(v domstate "$NAME")" != "shut off" ]]; then
    echo "$NAME is running and no Milkman run owns it; refusing to touch it" >&2; exit 1
  fi
  echo "held since $(date -Is) by ${USER} ($1)" >"$LOCK"
}
own_lock() { [[ -f "$LOCK" ]] || { echo "no Milkman run in progress (run prepare first)" >&2; exit 1; }; }

wait_for_harness() {
  for _ in $(seq 1 60); do
    "$RUN" ssh 'Test-Path C:\harness-ready.txt' 2>/dev/null | grep -q True && return 0
    sleep 10
  done
  echo "harness SSH did not come up" >&2; return 1
}

shutdown_vm() {
  "$RUN" ssh 'Stop-Computer -Force' >/dev/null 2>&1 || true
  for _ in $(seq 1 45); do [[ "$(v domstate "$NAME")" == "shut off" ]] && return 0; sleep 4; done
  v destroy "$NAME" >/dev/null
}

boot_from() {
  "$PG/snapshot.sh" revert "$1"
  v start "$NAME" >/dev/null
  wait_for_harness
  sleep 20
}

start_snapshot() {
  if [[ -n "${1:-}" ]]; then echo "$1"
  elif [[ -d "$STATE/snapshots/milkman-signed-in" ]]; then echo milkman-signed-in
  else echo claude-signed-in; fi
}

# --------------------------------------------------------------- actions
case "${1:-help}" in
  baseline)
    SNAP="${2:-claude-signed-in}"
    take_lock baseline
    trap 'shutdown_vm; "$PG/snapshot.sh" revert clean >/dev/null; rm -f "$LOCK"' EXIT
    boot_from "$SNAP"
    OUT="$HERE/baseline/$(date +%F)-$SNAP.winget-list.txt"
    mkdir -p "$HERE/baseline"
    WAIT_SECONDS=180 "$RUN" interactive 'winget list --accept-source-agreements --disable-interactivity' >"$OUT"
    echo "wrote $OUT"
    ;;

  prepare)
    SNAP="$(start_snapshot "${2:-}")"
    take_lock "prepare $SNAP"
    boot_from "$SNAP"
    # Test-only: onboarding's help line closes port 22 to everything but
    # Tailscale, which would lock the harness out. With the passt backend the
    # host reaches the guest from its default gateway, so allow just that.
    "$RUN" ssh '$gw = (Get-NetRoute -DestinationPrefix 0.0.0.0/0 | Select -First 1).NextHop; if (-not (Get-NetFirewallRule -Name milkman-harness-ssh -ErrorAction SilentlyContinue)) { New-NetFirewallRule -Name milkman-harness-ssh -DisplayName "milkman test harness SSH" -Direction Inbound -Protocol TCP -LocalPort 22 -RemoteAddress $gw,10.0.2.2 -Action Allow -Profile Any | Out-Null }'
    # Ship the local kit, for runs before the marketplace is pushed.
    TAR="$(mktemp --suffix .tar)"
    git -C "$KIT" archive --format=tar --prefix=beep-beginners/ HEAD >"$TAR"
    "$RUN" copy "$TAR" 'C:/Users/lawyer/beep-beginners.tar'
    "$RUN" ssh 'Remove-Item -Recurse -Force C:\Users\lawyer\beep-beginners -ErrorAction SilentlyContinue; tar -xf C:\Users\lawyer\beep-beginners.tar -C C:\Users\lawyer; Remove-Item C:\Users\lawyer\beep-beginners.tar; New-Item -ItemType Directory -Force C:\Users\lawyer\Desktop\setup | Out-Null'
    rm -f "$TAR"
    # v3: the profile step reads a memories file. The real one stays outside the
    # repo (BEEP_BEGINNERS_MEMORIES_FIXTURE, default ../memories.txt next to the
    # kit checkout); only a scrubbed example is committed. The workspace points
    # its marketplace at the local kit copy, since v3 isn't on GitHub yet.
    FIXTURE="${BEEP_BEGINNERS_MEMORIES_FIXTURE:-$KIT/../memories.txt}"
    "$RUN" ssh 'New-Item -ItemType Directory -Force C:\Users\lawyer\beep-test | Out-Null'
    if [[ -f "$FIXTURE" ]]; then
      "$RUN" copy "$FIXTURE" 'C:/Users/lawyer/beep-test/memories.txt'
      echo "memories fixture shipped to C:\\Users\\lawyer\\beep-test\\memories.txt"
    else
      echo "no memories fixture at $FIXTURE; the profile step will ask for a paste" >&2
    fi
    "$RUN" ssh '[Environment]::SetEnvironmentVariable("BEEP_BEGINNERS_MARKETPLACE_SOURCE", "C:\Users\lawyer\beep-beginners", "User"); [Environment]::SetEnvironmentVariable("BEEP_BEGINNERS_MEMORIES_FIXTURE", "C:\Users\lawyer\beep-test\memories.txt", "User"); [Environment]::SetEnvironmentVariable("BEEP_BEGINNERS_TEST", "1", "User"); New-Item -ItemType Directory -Force C:\Users\lawyer\beep-test | Out-Null'
    SHOTS="$STATE/shots/milkman-$(date +%Y%m%d-%H%M)"
    mkdir -p "$SHOTS"; echo "$SHOTS" >"$STATE/shots/milkman-current-dir"
    nohup bash -c "while true; do f=\"$SHOTS/\$(date +%H%M%S)\"; virsh -c $CONN screenshot $NAME \"\$f.ppm\" >/dev/null 2>&1 && magick \"\$f.ppm\" -resize 60% \"\$f.png\" && rm -f \"\$f.ppm\"; sleep 15; done" >/dev/null 2>&1 &
    echo $! >"$STATE/shots/milkman-recorder.pid"
    echo "VM up from $SNAP, kit at C:\\Users\\lawyer\\beep-beginners (commit $(git -C "$KIT" rev-parse --short HEAD))."
    echo "Screenshots every 15 s: $SHOTS"
    echo "View: setsid remote-viewer \$(virsh -c $CONN domdisplay $NAME) >/dev/null 2>&1 &"
    ;;

  vm) own_lock; "$RUN" ssh "${2:?command}" ;;
  vmi)
    # Like vm-run.sh interactive, but each call writes its own log file, so a
    # program that inherits the handle (say, an app started with `start`)
    # can't lock the log for every later call.
    own_lock
    CMD="${2:?command}" WAIT="${WAIT_SECONDS:-60}" ID="milkman-$$-$RANDOM"
    "$RUN" ssh "
\$log = 'C:\\Users\\lawyer\\$ID.log'
\$action = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument ('/c ' + '${CMD//\'/\'\'}' + ' > ' + \$log + ' 2>&1')
\$principal = New-ScheduledTaskPrincipal -UserId 'lawyer' -LogonType Interactive
Register-ScheduledTask -TaskName '$ID' -Action \$action -Principal \$principal -Force | Out-Null
Start-ScheduledTask -TaskName '$ID'
\$deadline = (Get-Date).AddSeconds($WAIT)
while ((Get-ScheduledTask -TaskName '$ID').State -eq 'Running' -and (Get-Date) -lt \$deadline) { Start-Sleep -Milliseconds 500 }
Start-Sleep -Seconds 1
Get-Content \$log -ErrorAction SilentlyContinue
\$result = (Get-ScheduledTaskInfo -TaskName '$ID').LastTaskResult
Unregister-ScheduledTask -TaskName '$ID' -Confirm:\$false
Remove-Item \$log -ErrorAction SilentlyContinue
exit \$result"
    ;;
  launch)
    # Start a GUI app in the desktop session with no output redirection.
    own_lock
    "$RUN" ssh "\$a = New-ScheduledTaskAction -Execute '${2:?exe path}'
\$p = New-ScheduledTaskPrincipal -UserId 'lawyer' -LogonType Interactive
Register-ScheduledTask -TaskName milkman-launch -Action \$a -Principal \$p -Force | Out-Null
Start-ScheduledTask -TaskName milkman-launch; Start-Sleep 3
Unregister-ScheduledTask -TaskName milkman-launch -Confirm:\$false"
    ;;
  type) own_lock; shift; "$PG/vm-type.sh" "$@" ;;

  shot)
    own_lock
    DIR="$(cat "$STATE/shots/milkman-current-dir" 2>/dev/null || echo "$STATE/shots")"
    f="$DIR/${2:-manual-$(date +%H%M%S)}"
    v screenshot "$NAME" "$f.ppm" >/dev/null && magick "$f.ppm" -resize 60% "$f.png" && rm -f "$f.ppm"
    echo "$f.png"
    ;;

  click)
    own_lock
    # Electron title bars ignore a bare jump-and-click, so glide in, hover, then click.
    q() { v qemu-monitor-command "$NAME" "$1" >/dev/null; }
    # The guest resolution changes when a viewer window resizes it, so read it each time.
    RES="$(mktemp --suffix .ppm)"; v screenshot "$NAME" "$RES" >/dev/null
    read -r W H < <(magick identify -format "%w %h\n" "$RES"); rm -f "$RES"
    mv() { local x=$(( $1 * 32767 * 100 / 60 / W )) y=$(( $2 * 32767 * 100 / 60 / H ))
      q "{\"execute\":\"input-send-event\",\"arguments\":{\"events\":[{\"type\":\"abs\",\"data\":{\"axis\":\"x\",\"value\":$x}},{\"type\":\"abs\",\"data\":{\"axis\":\"y\",\"value\":$y}}]}}"; }
    X=${2:?X} Y=${3:?Y}
    mv $((X - 8)) $((Y + 3)); sleep 0.4; mv $((X - 3)) $((Y + 1)); sleep 0.4; mv "$X" "$Y"; sleep 1
    q '{"execute":"input-send-event","arguments":{"events":[{"type":"btn","data":{"down":true,"button":"left"}}]}}'
    sleep 0.25
    q '{"execute":"input-send-event","arguments":{"events":[{"type":"btn","data":{"down":false,"button":"left"}}]}}'
    ;;

  evidence)
    own_lock
    OUT="${2:-$HERE/evidence/$(date +%F-%H%M).md}"
    mkdir -p "$(dirname "$OUT")"
    "$RUN" copy "$HERE/evidence.ps1" 'C:/Users/lawyer/beep-evidence.ps1'
    {
      echo "# Milkman proof evidence ($(date -u +%Y-%m-%dT%H:%MZ))"
      echo
      echo "Kit commit: \`$(git -C "$KIT" rev-parse --short HEAD)\`. Values are never recorded: sign-ins and keys appear as yes/no or counts."
      echo
      echo '```json'
      WAIT_SECONDS=1200 "$RUN" interactive 'powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\lawyer\beep-evidence.ps1'
      echo '```'
      echo
      echo "Seen over the harness SSH session (an unfiltered admin token):"
      echo
      echo '```json'
      "$RUN" ssh '[ordered]@{ helper_key_count = @(Get-Content C:\ProgramData\ssh\administrators_authorized_keys -ErrorAction SilentlyContinue | Where-Object { $_ -match "^(ssh-|ecdsa-|sk-)" }).Count; password_auth_off = [bool](Select-String -Path C:\ProgramData\ssh\sshd_config -Pattern "^PasswordAuthentication no" -Quiet) } | ConvertTo-Json'
      echo '```'
      echo
      echo "Screenshots: \`$(cat "$STATE/shots/milkman-current-dir")\` (kept out of the repo)."
    } >"$OUT"
    echo "wrote $OUT"
    ;;

  evidence-import)
    # When 1Password's access dialog needs the operator's own session, the
    # operator runs evidence.ps1 in their PowerShell window and this imports
    # the result: run.sh evidence-import [C:/path/evidence.json] [out.md]
    own_lock
    SRC="${2:-C:/Users/lawyer/beep-test/evidence.json}"
    OUT="${3:-$HERE/evidence/$(date +%F-%H%M).md}"
    mkdir -p "$(dirname "$OUT")"
    TMP="$(mktemp --suffix .json)"
    "$RUN" ssh "Get-Content '${SRC//\//\\}' -Raw" | tr -d '\r' >"$TMP"
    {
      echo "# Milkman proof evidence ($(date -u +%Y-%m-%dT%H:%MZ))"
      echo
      echo "Kit commit: \`$(git -C "$KIT" rev-parse --short HEAD)\`. Collected by evidence.ps1 in the operator's own desktop session (1Password trusts that session), imported from \`$SRC\`. Values are never recorded: sign-ins and keys appear as yes/no or counts."
      echo
      echo '\`\`\`json'
      sed -n '/^{/,$p' "$TMP"
      echo '\`\`\`'
      echo
      echo "Seen over the harness SSH session (an unfiltered admin token):"
      echo
      echo '\`\`\`json'
      "$RUN" ssh '[ordered]@{ helper_key_count = @(Get-Content C:\ProgramData\ssh\administrators_authorized_keys -ErrorAction SilentlyContinue | Where-Object { $_ -match "^(ssh-|ecdsa-|sk-)" }).Count; password_auth_off = [bool](Select-String -Path C:\ProgramData\ssh\sshd_config -Pattern "^PasswordAuthentication no" -Quiet) } | ConvertTo-Json'
      echo '\`\`\`'
      echo
      echo "Screenshots: \`$(cat "$STATE/shots/milkman-current-dir")\` (kept out of the repo)."
    } >"$OUT"
    rm -f "$TMP"
    echo "wrote $OUT"
    ;;

  reset)
    own_lock
    "$RUN" copy "$HERE/reset.ps1" 'C:/Users/lawyer/beep-reset.ps1'
    WAIT_SECONDS=300 "$RUN" interactive 'powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\lawyer\beep-reset.ps1'
    ;;

  finish)
    own_lock
    SAVE=""
    if [[ "${2:-}" == "--save" ]]; then
      SAVE="${3:?--save needs a snapshot name}"
      [[ "$SAVE" == milkman-* ]] || { echo "only milkman-* snapshots may be saved" >&2; exit 1; }
    fi
    [[ -f "$STATE/shots/milkman-recorder.pid" ]] && kill "$(cat "$STATE/shots/milkman-recorder.pid")" 2>/dev/null || true
    rm -f "$STATE/shots/milkman-recorder.pid"
    "$RUN" ssh 'Remove-Item C:\Users\lawyer\beep-evidence.ps1,C:\Users\lawyer\beep-reset.ps1 -ErrorAction SilentlyContinue' || true
    shutdown_vm
    [[ -n "$SAVE" ]] && "$PG/snapshot.sh" save "$SAVE"
    "$PG/snapshot.sh" revert clean
    rm -f "$LOCK"
    echo "VM reverted to clean${SAVE:+; saved $SAVE (local only)}."
    ;;

  *) sed -n '2,20p' "$0"; exit 0 ;;
esac
