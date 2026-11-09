# Windows VM proof

`run.sh` drives the practice-gateway Windows 11 VM from beep-effect
(`goals/practice-gateway/ops/vm/`). It calls those scripts and never copies
them. A run holds `~/VMs/practice-gateway/milkman.lock` from `prepare` to
`finish`. It refuses to start while the VM is running, or while a
practice-gateway proof is recording.

## A run

```sh
tests/vm/run.sh prepare            # from milkman-signed-in, else claude-signed-in
# drive onboarding in the VM; the operator signs in by hand when asked
tests/vm/run.sh evidence           # writes tests/vm/evidence/<date>.md
tests/vm/run.sh reset              # test repos, test SSH key, Tailscale login
tests/vm/run.sh finish [--save milkman-signed-in]
```

## Rules

- Never save `clean`, `claude-signed-in` or `agents-signed-in`; `finish`
  refuses anything but `milkman-*`. Save `milkman-signed-in` after the
  operator's first full sign-in, and again only when a sign-in is renewed.
  Keep it local.
- Agents never hold credentials. When a run reaches a sign-in page, stop and
  report the account and page. The operator signs in inside the VM.
- Test runs write only to the `beep-beginners-test` 1Password vault. Set
  `BEEP_BEGINNERS_AGENTS_VAULT` and `BEEP_BEGINNERS_KEY_VAULT` to it.
- Bitwarden import uses a generated fixture: `fixtures/make_bitwarden_fixture.py`
  (the password is in the script; it protects only fake items).
- Screenshots go under `~/VMs/practice-gateway/shots/milkman-*`, never into
  the repo. Evidence records yes/no and counts, never values.
- One run per release clicks through the folder picker by hand. The others
  set `BEEP_BEGINNERS_WORKSPACE`.

## What `milkman-signed-in` holds (saved 2026-11-08)

Claude desktop and CLI signed in to the operator's account; Chrome with the
Claude extension installed and linked; GitHub CLI signed in as the test account
(scopes include `delete_repo`); 1Password (1password.com edition) signed in
with Windows Hello, the Balanced preset and the CLI integration on; a Windows
Hello PIN for `lawyer` (value in `~/VMs/practice-gateway/state/lawyer-pin`);
Tailscale signed in on the operator's tailnet; user settings with auto mode and
Opus 5.5 at medium effort; every tools.yaml tool installed. No workspace, no
onboarding state, no test repos. A run from it still exercises every onboarding
step; the sign-in steps just find their sign-ins done.

1Password's access dialogs are per program and per Windows logon session. The
harness's scheduled tasks start a new logon session each time, so `op` calls
from `run.sh vm`/`vmi` get the account-password dialog and time out. Collect
1Password evidence from the operator's own PowerShell window with
`C:\Users\lawyer\beep-test\ev.cmd` style launchers and import it with
`run.sh evidence-import`.

## Baselines

`baseline/` holds `winget list` inventories of the start snapshot. The
2026-11-06 pre-tools inventory came before Chrome, VS Code, PowerShell 7 and
Windows Terminal were added to the snapshots (D32).

## The v3 proof (2026-11-09)

v3's proof drove the kit's scripts straight from the harness instead of the
desktop app: `run.sh prepare milkman-signed-in` ships the kit and the memories
fixture (`BEEP_BEGINNERS_MEMORIES_FIXTURE`, default `../memories.txt` beside the
kit checkout, never committed) and sets the test environment variables for the
`lawyer` user (`BEEP_BEGINNERS_MARKETPLACE_SOURCE` pointing at the local kit
copy, `BEEP_BEGINNERS_KIT_REF=main`, `BEEP_BEGINNERS_TEST=1`). Each step then ran
as a PowerShell script through `run.sh vmi` in the interactive logon session,
where `gh` can read its credential store. One headless `claude -p` session in
the workspace checked the SessionStart hook and the loaded skills; a second
would have cost more of the operator's weekly limit, which that session showed
was already spent.

What the agent-driven onboarding adds on top of the scripts (the interview,
the welcome, the D57 hand-off into the explore skill) is prompt text in the
onboarding skill; the scripts it calls are what this proof exercised.

Steps for a rerun: `prepare`, then the `proof*.ps1` scripts the session wrote
to `C:\Users\lawyer\beep-test\` (kept out of the repo; the evidence file
lists what each did), then `evidence`, `reset`, `finish`.
