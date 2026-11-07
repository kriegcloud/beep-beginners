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

## Baselines

`baseline/` holds `winget list` inventories of the start snapshot. The
2026-11-06 pre-tools inventory came before Chrome, VS Code, PowerShell 7 and
Windows Terminal were added to the snapshots (D32).
