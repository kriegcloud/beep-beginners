# Maintaining the kit

## Layout

```text
.claude-plugin/marketplace.json   the marketplace; every plugin by relative path
plugins/
  onboarding/   one-time setup: tools.yaml, scripts/, template/, seeds/, the runbook skill
  guards/       PreToolUse guard (git, deletes, secrets), SessionStart/SessionEnd upkeep
  explore/      explorations -> goals, plain-English packets, packet.py bookkeeping
  unslop/       the writing pass every user-facing text goes through
  helper/       help requests, helper access on/off, teach-back
  pokeseller/   Mercari listing skill and the listing checker hook
  job-hunt/     the morning job-hunt routine
tests/vm/       Windows VM proof runner (calls beep-effect's VM scripts)
docs/           decisions, research, this file
```

## How changes reach a workspace

A workspace's `.claude/settings.json` registers this repo as the
`beep-beginners` marketplace with `"autoUpdate": true` and enables the
plugins by name. Plugins have no `version` field, so every commit to `main`
counts as a new version. Claude Code checks for updates during a session and
uses them from the next one. Nobody merges anything into the workspace.

Files that onboarding copied from `plugins/onboarding/template/` (root
`AGENTS.md`, settings, `.gitignore`) belong to the workspace after creation.
To change behavior for existing workspaces, change a plugin (a skill, a hook,
a script), not the template.

## Rules for every change

- Hooks and scripts are Python run with `uv run --script`, with PEP 723
  metadata. Hooks use the standard library only, so they never download
  anything mid-session.
- Hooks are exec form (`"command": "uv"`, `"args": [...]`) and match
  `Bash|PowerShell`, because PowerShell is the main shell on Windows.
  Guards block with exit 2 and never answer "ask".
- Every deny rule in a settings file has a `Bash(...)` and a `PowerShell(...)`
  form.
- Nothing personal goes in this repo. Seeds hold rules, not names of the
  user, places, money amounts, account ids or buyer data.
- Run `unslop` on anything a user will read.

## Tests

```sh
uv run --script plugins/guards/tests/test_rules.py
uv run --script plugins/pokeseller/tests/test_listing_check.py
claude plugin validate .
tests/vm/run.sh --help        # Windows proof, see tests/vm/README.md
```
