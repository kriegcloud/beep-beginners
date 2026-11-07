# Decisions

This log is for whoever maintains the kit. The person who uses a workspace
never needs to read it.

The kit started from a private spec with 23 numbered decisions, settled in two
grilling sessions on 2026-11-06. That spec holds personal details, so it stays
out of this public repo. Entries below record what changed after the
2026-11-06 research pass (`docs/research/2026-11-06-starter-kit-research.md`)
and the grilling round that followed. A number in brackets names the spec
decision an entry amends.

## 2026-11-06

### D24. Safety layer is auto mode, deny rules, then hooks [amends 10]

- **Question.** Hooks may not fire in the desktop app's Code tab on Windows
  (anthropics/claude-code#96496), and a hook that matches only `Bash` misses the
  PowerShell tool. What is the main safety layer?
- **Answer.** Onboarding sets `defaultMode: "auto"` in the user's
  `~/.claude/settings.json`, because a project settings file can't set auto mode.
  Deny rules are the hard floor, and each `Bash(...)` rule has a `PowerShell(...)`
  twin, because a Bash-only deny turns the PowerShell tool off. The Python hooks
  are a backup: they match `Bash|PowerShell|Read|Edit|Write`, deny with exit 2, and
  never answer "ask", because auto mode ignores an "ask". A SessionStart hook
  prints one line saying the guards are on, so a session where hooks don't run
  is easy to spot.
- **Rejected.** `acceptEdits` plus an allowlist, as decision 10 first said.
  It means more prompts for someone who would approve them without reading,
  and it relies on hooks that may not fire.

### D25. Pushing happens at session end, with a catch-up at session start [amends 16]

- **Question.** A Stop hook runs after every reply, not once per session, and
  the commands it runs skip permission checks. How should the off-machine
  backup work?
- **Answer.** A SessionEnd hook pushes to `origin`. A SessionStart hook pushes
  anything left unpushed from a session where hooks did not run. Each push
  has a short timeout and does nothing when there is nothing to push. The
  changelog for the user is regenerated in the same step.
- **Rejected.** A Stop hook push, which runs every reply and can hang on
  Windows (#77078). A scheduled task, which adds another moving part.

### D26. Bootstrap is one pasted sentence

- **Question.** The user never types a command, and a bare machine has no
  workspace for project settings to load from. How does the kit arrive?
- **Answer.** The helper texts one sentence. The user opens the Claude desktop
  app in Code mode on an empty folder and pastes it. The agent installs the
  Claude Code CLI with the native installer, adds this marketplace, and
  installs the onboarding plugin at user scope. Onboarding then takes over.
  Adding the marketplace through the CLI also covers the report that the desktop
  app on Windows doesn't register `extraKnownMarketplaces` (#70318, #16870).

### D27. OpenKnowledge stays the docs app [confirms 20]

- **Question.** Research found OpenKnowledge young: 0.x, Windows support since
  August 2026, recent data-loss bugs, no winget package, and it writes agent
  config files into the folder it opens. Switch to Obsidian?
- **Answer.** No. OpenKnowledge stays the default. Onboarding installs it from
  its per-user GitHub release (`OpenKnowledge-Setup-x64.exe`, no UAC) and says
  in one sentence that it may become the default app for `.md` files. The
  template's `.gitignore` covers `.ok/` and the agent config files it generates
  (`.cursor/`, `.codex/`, `opencode.json`). Obsidian is installed only on request.

### D28. Fresh history by pruning, deleting `.git`, then `git init`

The old fork clone's history is still in beep-effect, because `da69ce5cd0` is an
ancestor of beep-effect's `main`. So the clone was pruned to the kept parts, its
`.git` was deleted, and a new repository was started with the first commit
"Starter kit, pruned from beep-effect @ da69ce5cd0". No old objects exist
locally that could be pushed.

### D29. Software list additions [amends the software table]

Added: Google Chrome (needed for Claude in Chrome, missing from the test VM),
Windows Terminal (detect it, install it if missing), PowerShell 7 and VS Code.

### D30. Matt Pocock's skills come from Anthropic's official marketplace [amends 19]

Enable `mattpocock-skills@claude-plugins-official`. That marketplace is
registered by default and auto-updates, and the author's README points
Claude Code users there. `git-guardrails-claude-code` isn't in that plugin, so
nothing needs excluding. `grill-me`, `teach`, `handoff` and `wait-what` can only
be started by typing them.

### D31. VM proof data

The Bitwarden step imports a generated, password-protected Bitwarden JSON
fixture with fake items into the `beep-beginners-test` vault, so no Bitwarden
account is involved. The "done" run answers "Claude only". One extra run answers
"ChatGPT" and checks the Codex and CLIProxyAPI installs up to the sign-in page.

### D32. Test VM snapshots carry the QA tools

At the operator's request, the practice-gateway VM's `clean`, `claude-signed-in`
and `agents-signed-in` snapshots were re-saved with Chrome, VS Code,
PowerShell 7 and Windows Terminal installed. Before each re-save, its prior state
was kept as `pre-tools-<name>`. beep-effect's `harness.template.ps1` installs the
same tools, so a rebuilt VM gets them. Onboarding's detection therefore has to
recognize and skip these tools on the test VM.

### D33. Git pushes over HTTPS through the GitHub CLI

Onboarding still makes an SSH key in 1Password and adds it to GitHub, as the
spec asks. Git itself pushes over HTTPS with `gh auth setup-git`. With
1Password's SSH agent, every push would wait for a 1Password approval, so the
automatic end-of-session backup (D25) would stall. Using that agent on Windows
also means disabling Windows' own SSH agent service, which needs admin rights.

### D34. Build notes that changed the phase 3 tree

- `template/` lives at `plugins/onboarding/template/`. Claude Code copies only
  a plugin's own folder into its cache, so a top-level `template/` would never
  reach the user's machine.
- Claude loads project settings only from the folder a session opens on. So
  `pokeseller` and `job-hunt` are enabled for the whole workspace by the seed,
  not per folder. They only do anything for listing drafts and job-hunt
  requests. Per-folder rules still load only in their folder, through each
  folder's `AGENTS.md` and `CLAUDE.md`.
- `CHANGELOG-FOR-ED.md` is gitignored and rebuilt from commit messages at the
  start and end of each session. Committing it would add a commit to the
  history on every session.
- Test runs set `BEEP_BEGINNERS_AGENTS_VAULT` and `BEEP_BEGINNERS_KEY_VAULT` to
  the `beep-beginners-test` vault, so they never write to a real vault.

## Facts from research that shape the build

- 1Password Individual is about $36 for the first year, then about $48 a year.
  The cost question to the user states both.
- Bitwarden must be exported as encrypted JSON (password protected) for
  1Password's import to work. An unencrypted JSON export doesn't import.
- A 1Password service account can't see the built-in Personal vault, and its
  vault access can't be changed later. Make the Agents vault first.
- If the user's Windows account is an administrator, the helper's SSH key goes
  in `C:\ProgramData\ssh\administrators_authorized_keys` with the documented
  `icacls` permissions. sshd is limited to Tailscale by a firewall rule that
  allows only `100.64.0.0/10`, not by `ListenAddress`. Tailscale SSH can't act
  as a server on Windows, and Windows Home can't host RDP.
- Plugins load from this marketplace by relative path. The template sets
  `autoUpdate: true` on the marketplace entry and leaves plugin `version` unset,
  so every commit counts as an update.
