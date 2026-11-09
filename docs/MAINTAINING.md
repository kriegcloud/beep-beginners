# Maintaining the kit

## Layout

```text
.claude-plugin/marketplace.json   the marketplace; every plugin by relative path
plugins/
  kit/          the kit: everything that shares one script
    scripts/kit.py              the command layer (D51); kitlib/ holds its modules
    scripts/{detect,tools,state,workspace,pick_folder}.py   onboarding's scripts
    hooks/hooks.json, rules.py  PreToolUse guard rules, SessionStart/SessionEnd via kit.py hook
    skills/                     onboarding, explore, goal, project, explain, kit-grill, caretaker
    templates/                  exploration, goal, project-python, project-ts (with WORKFLOW.yml.tmpl)
    template/                   the workspace onboarding copies (AGENTS.md slots, settings, CI, NEEDS-YOU)
    tools.yaml                  the software list
    chores.yaml                 the chores (D52)
    examples/profile-card-reseller/   the worked example of profile -> skills (scrubbed, no real person)
    MANIFEST                    every plugin file, for `kit caretaker fetch` (D45)
    tests/                      pytest scripts
  unslop/       the writing pass every user-facing text goes through
  helper/       help requests, helper access on/off, teach-back
tests/vm/       Windows VM proof runner (calls beep-effect's VM scripts) and the cloud proof notes
docs/           decisions, research, this file
.github/        the kit's own CI: the same security workflow it ships, plus tests
```

## How changes reach a workspace

A workspace's `.claude/settings.json` registers this repo as the
`beep-beginners` marketplace with `"autoUpdate": true` and enables `kit`,
`unslop` and `helper` by name. Plugins have no `version` field, so every
commit to `main` counts as a new version. Claude Code checks for updates
during a session and uses them from the next one. The caretaker fetches the
kit fresh on every cloud run (D45). Nobody merges anything into a workspace.

Files that onboarding copied from `plugins/kit/template/` (root `AGENTS.md`,
settings, `.gitignore`, the CI workflows) belong to the workspace after
creation. To change behavior for existing workspaces, change a plugin (a
skill, a hook, the script, `chores.yaml`), not the template.

## Rules for every change

- Hooks and scripts are Python run with `uv run --script`, with PEP 723
  metadata. `kit.py` and its hooks use the standard library only, so they
  never download anything mid-session or in the sandbox. `detect.py` and
  `tools.py` may use pyyaml; they only run during onboarding.
- Hooks are exec form (`"command": "uv"`, `"args": [...]`) and match
  `Bash|PowerShell`, because PowerShell is the main shell on Windows.
  Guards block with exit 2 and never answer "ask".
- Every deny rule in a settings file has a `Bash(...)` and a `PowerShell(...)`
  form.
- Every skill calls `kit.py` through `${CLAUDE_PLUGIN_ROOT}`, never `git
  commit` or `gh pr`. GitHub goes through `gh api` REST only (D51).
- Nothing personal goes in this repo. The worked example is a made-up person.
  Real memories live outside the repo and reach the VM through a gitignored
  fixture path.
- Run `unslop` on anything a user will read.
- When you add a file under `plugins/kit/`, regenerate `MANIFEST`:
  `KIT_WRITE_MANIFEST=1 uv run --script plugins/kit/tests/test_kit.py`.

## Tests

```sh
uv run --script plugins/kit/tests/test_rules.py      # guard rules
uv run --script plugins/kit/tests/test_landing.py    # kit land / kit sync against real git repos
uv run --script plugins/kit/tests/test_kit.py        # packets, projects, chores, needs-you, explain, profile, gate, manifest
uv run --script plugins/kit/tests/test_elevated_batch.py   # needs pwsh
claude plugin validate .
tests/vm/run.sh --help        # Windows proof, see tests/vm/README.md
```

`.github/workflows/tests.yml` runs the same, plus a smoke run of `kit` on a
fresh template and a build of both project templates.
