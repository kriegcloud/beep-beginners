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

### D35. A PowerShell bootstrap, the one script that isn't Python [amends 8]

The first VM run (2026-11-06) showed admin prompts before onboarding had even
started. Git for Windows' installer asks for admin even with
`winget --scope user`. uv's winget package pulls in the Visual C++ runtime,
which also asks for admin. `bootstrap.ps1` installs Claude Code, uv (from
its own installer) and Git (the portable build, unpacked under
`%LOCALAPPDATA%\Programs\Git`) for the current user only, then adds the
marketplace and the onboarding plugin. It has to be PowerShell because uv,
and with it Python, is one of the things it installs. The pasted sentence
became shorter: it runs this script. The Visual C++ runtime moved into the
one elevated batch.

## 2026-11-07

### D36. 1Password on Windows: the 1password.com edition, a Hello PIN, and `op vault list` [amends 13]

The second VM run (2026-11-07) spent two hours on step 9. What was learned:

- Only the 1password.com edition (winget `AgileBits.1Password`) counts as
  installed. The Microsoft Store edition on the test VM looked present to
  detection, so the install was skipped, and the CLI could not reach it.
- 1Password's CLI integration on Windows needs Windows Hello. Without a PIN
  the app never shows its "Access Requested" dialog. `detect.py` now reports
  `windows_hello`, and the skill sends the user to Settings > Accounts >
  Sign-in options first when it is false.
- `op whoami` on its own never asks the app for access and only prints
  "account is not signed in". A data command does: the check is
  `op vault list`, and the first run asks for the account password (it gives
  up after about a minute). Every program that calls `op` (PowerShell, cmd,
  Claude) is approved once with Authorize plus Hello.
- Enabling Hello switched the app's unlock preset to Strict, which re-prompts
  on every `op` process. Onboarding tells the user to pick Balanced when the
  "Pick your preferred way to unlock" sheet appears.
- The errors the agent saw ("cannot connect to 1Password app", "account is
  not signed in") were not a Claude Code sandbox: on native Windows Claude
  Code runs commands unsandboxed (Claude Code docs, sandboxing page).

### D37. 1Password MCP for Claude Desktop: proposed, not yet built

The 1Password app now ships a local MCP server (Settings > Developer >
"Integrate with MCP clients"). It would give the Claude desktop app's chat
mode, which has no shell, the same reference-based access that Code mode gets
from the CLI. Benjamin asked for it on 2026-11-07. Open before it is added:
which vault it may see (the Agents vault only, like the CLI), whether it is
set up during onboarding or on first need (as decision 20 does for
OpenKnowledge's MCP), and how approvals work (Hello per session, like the
CLI). Until then agents use the CLI route from decision 13.

### D38. Run findings fixed in the kit (2026-11-07)

- Installers run with hidden consoles; rustup uses `--profile minimal`
  (rust-docs alone took about 17 minutes on the VM).
- The elevated batch prints what it is installing instead of a blank window,
  and installs Tailscale with `TS_NOLAUNCH=1` so its welcome window stays
  shut. Windows cancels the UAC prompt by itself after about two minutes.
- The seed question recommends Yes; the accounts question keeps Bitwarden
  even when no app is detected; the README names the `</>` Code button,
  because the desktop app opens on its chat tab, which has no shell.
- Step 9 opens the app with `onepassword://`, not `1password://`.
- `workspace.py create` installs every enabled plugin at project scope
  (`claude plugin install <p> --scope project`). Enabling them in settings
  alone left the first session with `plugin-cache-miss` and no kit skills;
  after the installs a session loaded all 39 plugin skills.
- Step 3 trusts `facts.claude_in_chrome`, not a Claude in Chrome tool answer:
  on the VM the tool reached the host's Chrome through the shared account.

### D40. Sessions run Opus 5.5 at medium effort

The desktop app's Code tab defaulted the test VM's sessions to the top model at
high effort, and one onboarding used most of a weekly limit. Benjamin ruled on
2026-11-07: every session in the kit runs `claude-opus-5-5` at `medium`.
`bootstrap.ps1` writes `model` and `modelSettings` into the user settings
before the first session, `workspace.py user-settings` keeps them, and the
workspace and PokeLedger settings carry the same values.

### D39. Proposals to make onboarding faster for the user (2026-11-07, open)

Raised by Benjamin while signing in on the test VM. Not built yet; each needs
a yes before it changes the kit.

- **Sign-in sprint.** Open GitHub, Claude, 1Password and Tailscale sign-in
  pages in one Chrome window at the start, let the user work through them
  while the installs run, and have the agent verify each afterwards.
- **Tailscale pre-auth key.** The helper issues a short-lived pre-auth key;
  onboarding runs `tailscale up --authkey` and the user never sees a Tailscale
  sign-in. This replaces the "own tailnet plus share" setup in decision 22,
  which is how the 2026-11-07 run ended up anyway.
- **One GitHub login with every scope.** Ask for `repo`, `admin:public_key`,
  `workflow` (and `delete_repo` in tests) in the first `gh auth login`, so
  there is never a second device-code round.
- **1Password service account for unattended work only.** Hooks and scheduled
  jobs could use a service account scoped to the Agents vault. Interactive
  agent work keeps the desktop integration: with the Balanced preset and
  Windows Hello it costs one Authorize per program per day and no password
  after the first time. Bypass permissions mode stays out (decision 10);
  auto mode already ran the whole onboarding without permission prompts.
- **Claude in Chrome does the form work** (device codes, account pickers,
  Add buttons), as the spec intended; the extension just has to be installed
  locally first, which step 3 now checks.

### D41. The 2026-11-07 run is the accepted proof

Benjamin accepted the 2026-11-07/08 VM run (`tests/vm/evidence/2026-11-08-0019.md`)
as the proof for this release, with two manual steps beyond the four the spec
lists: setting a Windows Hello PIN and choosing 1Password's Balanced preset.
Both are now onboarding-guided user steps. A later release may re-prove with
the pre-auth-key and sign-in-sprint ideas from D39.

## 2026-11-08

Settled in a grilling session with Benjamin on 2026-11-08, after the kit was
proven for one user (D41). The problem being solved: every simplified setup
Benjamin had made for friends drifted over time, because nobody maintained it,
the friends didn't know what to ask for, and agents don't take initiative
unless something tells them to. Two fact checks fed these entries: Claude
Code's cloud scheduled tasks (code.claude.com/docs/en/routines) and GitHub's
free-plan security features (see the facts section at the end).

### D42. The kit is generic; each user gets a profile [amends 1, 14, the Ed-specific plugins]

- **Question.** The spec and the first release were written for one person,
  with his listing and job-hunt plugins in the marketplace. The kit is for
  several friends. What is it now?
- **Answer.** The kit holds only machinery: onboarding, explore and goals,
  guards, the caretaker, chores, security, the explain skill, unslop, helper.
  Onboarding builds a profile per user (D55) and generates their personal
  skills into their own workspace's `.claude/skills/`. `pokeseller` and
  `job-hunt` leave the marketplace and become the worked example of
  profile-to-skills generation. No live workspace depends on them: the kit has
  only run on the test VM.
- **Rejected.** Keeping it one person's kit and forking by hand for the next
  friend, which repeats the hand-holding the kit exists to remove. Keeping the
  Ed plugins in the marketplace as opt-in personas, which is more to maintain
  for a shape only one friend has.

### D43. One private repo per user, projects under `projects/<name>` [amends 3]

- **Question.** Where do the apps and automations a user builds live? The hub
  is markdown packets and Python scripts.
- **Answer.** Everything is one repository. The hub stays at the root
  (explorations, goals, docs, profile). Each app or automation lives under
  `projects/<name>` with its own `AGENTS.md` and `CLAUDE.md`, its own stack
  (D56) and its own tests. No turborepo, no uv workspace, no Node requirement
  for the hub. CI runs per changed folder with path filters. Benjamin's
  reasoning: by the time a user needs several repositories they have become
  intermediate, and the kit stops at beginners. A second repository for a
  learning project (PokeLedger in the spec) stays allowed because it has to sit
  on a profile for employers; that is a user-facing reason, not a layout one.
- **Rejected.** A turborepo (Node, a lockfile and Dependabot churn on tooling
  the user never asked for, and awkward for Python). A uv workspace (makes any
  TypeScript project second class). Separate repositories per app (chosen
  first in the session, reversed by Benjamin for the reason above).

### D44. Unattended work runs on Claude cloud scheduled tasks plus session-start chores

- **Question.** Agents exist only while a session is open. Merging updates,
  watching checks, triaging alerts and sweeping stale work have to happen when
  the user is away. Where does that run?
- **Answer.** A Claude Code cloud scheduled task (the `/schedule` feature, in
  research preview on 2026-11-08) is the caretaker. It runs on Anthropic's
  infrastructure against the user's own subscription with no API key, clones
  the repository fresh each run, and reaches GitHub through the Claude GitHub
  App or the user's `gh` token. Anything that needs the local machine (plugin
  updates, backup check, OneDrive drift) runs as the first chore of a desktop
  session (D52).
- **Rejected.** `claude-code-action` in GitHub Actions: officially supports a
  subscription OAuth token from `claude setup-token`, but onboarding would
  have to mint a long-lived token, store it as a repository secret, rotate it,
  and spend the user's Actions budget. Session-start only: a user who opens
  Claude twice a month leaves PRs and alerts sitting for weeks.

### D45. The caretaker fetches the public kit at run start

- **Question.** Cloud tasks do not install marketplace plugins.
  Cloud runs ignore `enabledPlugins` and `extraKnownMarketplaces` and load
  only the clone's `CLAUDE.md`, `.claude/skills/`, and the hooks and
  permission rules in `.claude/settings.json`. How does the caretaker get the kit?
- **Answer.** The task's prompt starts with a shallow clone of
  `kriegcloud/beep-beginners` into the sandbox and runs the kit script and
  skills from there. Always current, nothing vendored into the user's
  repository, no commit churn. The kit is public, so the sandbox's GitHub proxy
  should allow the clone; the build proves this on a test task before anything
  depends on it.
- **Rejected.** A session-start chore that vendors the caretaker skill into
  the workspace and commits it (fills history with kit updates, and a user who
  stays away a month runs a stale caretaker). Moving the caretaker to GitHub
  Actions (D44).

### D46. What the caretaker may do with nobody awake

- **Answer.** Unattended: merge Dependabot PRs and agent-opened PRs when every
  required check is green (through `kit pr merge`, D49); retry a flaky check
  once; fix a failing lint or test in a kit-made PR; read Dependabot alerts;
  sweep stale packets; write `NEEDS-YOU.md` (D53) and the weekly note. Never
  unattended: anything that changes a price, publishes, sends, deletes data,
  adds a paid service, or where checks stay red after one fix attempt. Those
  become items the user sees at the start of their next session.
- **Rejected.** Bot PRs only (an app fix sits unmerged until the user opens
  Claude). Merge anything green (a green check is not "the app still works").

### D47. Caretaker cadence: a daily sweep plus a PR-opened trigger

- **Answer.** Two cloud tasks, both created by onboarding. A daily morning
  sweep does merges, Dependabot, alerts, staleness, `NEEDS-YOU.md`, and on
  Mondays the weekly note. A GitHub trigger on "pull request opened" (sessions
  and Dependabot both open PRs) merges a green PR within the hour. The
  minimum schedule for cloud tasks is one hour; GitHub-event and manual fires
  are also capped per hour.
- **Rejected.** Daily only (slow for app fixes). Hourly (24 mostly empty runs
  a day against the user's subscription).

### D48. Packets land on main; code lands through short-lived PRs [amends 16, D25]

- **Question.** The hub commits at checkpoints and pushes at session end. Code
  needs checks before it lands. One repository now carries both.
- **Answer.** Changes under `explorations/`, `goals/`, `docs/` and the profile
  keep committing to `main` at checkpoints, with the session-end push. Changes
  under `projects/` go on a branch named for their goal; the session-end hook
  pushes that branch and opens a PR through `kit pr open`; the caretaker
  merges it when green. The kit script picks the path by what changed, so
  neither the user nor the agent decides.
- **Rejected.** Everything through PRs (half-finished sessions leave open PRs,
  and the backup push becomes a branch push plus a PR). Everything straight to
  main (a broken app reaches main before anyone looks).

### D49. The kit enforces the merge gate; no GitHub upgrade

- **Question.** On a Free personal account, private repositories have no
  branch protection and no enforced rulesets, so GitHub cannot require checks
  before a merge. Who does?
- **Answer.** Merging only happens through `kit pr merge`. It reads the PR's
  check runs over `gh api`, refuses unless every required check is green and
  no gitleaks finding is open, and merges over REST. The guards plugin denies
  raw `gh pr merge` and `gh api .../merge` so no agent can go around it. The
  caretaker and desktop sessions share the one code path.
- **Rejected.** GitHub Pro at about $4 a month per user for protected
  branches (another subscription the user has to approve and keep). A public
  repository (free rulesets and scanning, but the hub holds the user's
  profile, job hunt and business notes).

### D50. Security: prevent locally, scan with free tools in CI

- **Question.** GitHub Secret Protection and Code Security are paid, and a
  Free personal account cannot buy them for private repositories at all. What
  is the stance?
- **Answer.** The risk that matters is an agent committing a secret, so a
  PreToolUse guard runs gitleaks on staged files before any `git commit` and
  blocks on a finding. gitleaks goes on the software list through `tools.yaml`.
  CI in the workspace runs gitleaks, Semgrep CE, zizmor (on the workflow
  files themselves) and osv-scanner, with Dependabot version and security
  updates. All are free for personal private repositories (gitleaks-action
  needs no license key there; zizmor runs with `advanced-security: false`
  because GitHub gates SARIF upload behind paid code scanning). Onboarding enables Dependabot alerts and
  security updates over the API, since private repositories need that done by
  hand, and commits `.github/dependabot.yml`. The kit repository runs the same
  CI on itself. Secret-scanning alerts are not read from GitHub: that API
  returns 404 where secret scanning isn't enabled.
- **Rejected.** Paying for GitHub Advanced Security (not purchasable here,
  and $19 to $49 per committer a month where it is). Making repositories
  public (D49).

### D51. One plugin-shipped `kit` script is the command layer

- **Question.** beep-effect's edge is its commands: bootstrap a packet, open a
  PR, watch CI. The kit had one script, `packet.py`, called from skills.
- **Answer.** A single uv-run Python entry point in the plugin with
  subcommands: `kit explore new`, `kit goal graduate`, `kit project new`,
  `kit pr open`, `kit pr watch`, `kit pr merge`, `kit chores run`,
  `kit needs-you`, `kit explain`. Skills call it through
  `${CLAUDE_PLUGIN_ROOT}`, so it updates with the marketplace, and the
  caretaker runs it from its kit clone (D45). `packet.py` folds into it. All
  GitHub calls use `gh api` REST, because the cloud sandbox's GitHub proxy
  rejects GraphQL and `gh pr` fails there. The user never sees any of it.
- **Rejected.** An installable `uv tool` CLI (updates separately from the
  plugins, so kit and CLI drift). Skills only with raw git and gh (the setup
  that got messy: no deterministic steps, no tests).

### D52. A kit-owned `chores.yaml`; stale work gets a question, never a silent archive

- **Answer.** The kit ships `chores.yaml`: for each chore its cadence, its
  command, and the one line to tell the user. Desktop sessions run the most
  overdue chore at session start, capped at about two minutes, and say one
  line about it. The caretaker runs the ones that don't need the machine.
  Staleness (an exploration untouched for 30 days, a goal with no progress)
  produces a question in the next session: keep, park or drop. Nothing moves
  or is deleted without a yes. Fixes to the list reach every workspace
  through the marketplace.
- **Rejected.** Auto-parking stale packets (the user may not notice something
  they cared about got parked). A per-workspace `CHORES.md` the agent edits
  (kit fixes never reach existing workspaces, which is how things drifted
  before).

### D53. `NEEDS-YOU.md` is how the caretaker reaches the user

- **Question.** Notifications from cloud tasks are not documented. How does
  "this needs you" reach someone who never reads GitHub?
- **Answer.** The caretaker commits a short plain-language list to the hub:
  one item per decision, each with a brief from the explain skill (D54). The
  session-start hook opens every session with it ("Two things need you:
  ..."). Resolved items move to the changelog. The weekly "what happened" note
  lives in the same file. Nothing reaches the user between sessions, which
  matches how they already use Claude: they come to it.
- **Rejected.** GitHub Issues with email (teaches them to read GitHub, and the
  mail looks like spam from a bot). Texting the helper (routes routine
  decisions through Benjamin again).

### D54. Decision briefs from a learner profile, plus a running glossary

- **Question.** Agents have to explain tradeoffs and technical decisions in
  terms each user understands.
- **Answer.** Root `AGENTS.md` gets a "how I learn" slot onboarding fills:
  background, analogies that work, how much detail they want. An `explain`
  skill (and `kit explain`, which renders the template) produces a
  fixed-shape brief for anything non-trivial: what I'm deciding; your options
  in one line each; what each costs you in time, money or risk; what I
  recommend and why; what you'd have to do. New terms get added to
  `GLOSSARY.md` the first time they appear. Unslop runs on all of it.
- **Rejected.** An analogy-first rule with no fixed shape (quality depends on
  the session's mood and nothing accumulates). A weekly digest only
  (decisions get explained after the user could weigh in).

### D55. Profiles come from a Claude memory import plus a short interview

- **Answer.** Onboarding asks the user to export or paste their Claude
  memories, reads them, drafts the profile, then asks only what is missing
  in five or six questions: what they do, what they want to build or learn,
  how they like to be helped. The profile fills the `AGENTS.md` slots
  (about, how I learn, folders) and generates personal skills into the
  workspace's `.claude/skills/`. The old `pokeseller` and `job-hunt` plugins
  are the reference output for a user with Ed's memories.
- **Rejected.** Interview only (loses the richest signal about how they
  think). Benjamin writing a profile per friend by hand (keeps him in the
  loop for every friend).

### D56. App stack: Python by default, TypeScript when the goal needs a web UI

- **Answer.** Scripts, data work, automations and report feeds: Python with
  uv, ruff and pytest. Anything with a browser UI: TypeScript with bun, Biome
  and Vitest. Two `projects/` templates with one CI skeleton (gitleaks,
  Semgrep, zizmor, osv-scanner, Dependabot, tests). The goal skill picks and
  says why in one line; the user never chooses.
- **Rejected.** Python only (web UIs become Streamlit or server templates).
  TypeScript only, Benjamin's own stack (the user can't read any of it, and
  the data-analyst crowd loses the Python they're learning).

### D57. The first session ends with the user's own exploration packet

- **Question.** The point of the kit is the "aha" moment. Setup ended with a
  working machine and a README of prompts to try.
- **Answer.** Onboarding's interview already surfaces what the user wants to
  build or figure out. The last onboarding step hands off into the explore
  skill on that topic, so the first session ends with a plain-language packet
  they can open in OpenKnowledge, committed and backed up, and one line on
  what just happened to it.
- **Rejected.** A guided tour (a lecture about the system instead of the
  system doing something for them). Nothing scripted (the user who doesn't
  know what they don't know stalls at the blank page).

### D58. Where this round is recorded

These entries, plus `PROMPT.v3.md` in Benjamin's private folder as the build
brief. Nothing pushed; Benjamin reviews both. The v2 decisions not named
above stand: Windows first, operator and mentor modes, the help channel, the
software list, the VM proof.

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
- Claude Code cloud scheduled tasks (verified 2026-11-08, research preview):
  run on Anthropic infrastructure against the subscription, need a claude.ai
  login (not an API key), clone the repository fresh each run and push
  `claude/`-prefixed branches, load the clone's `CLAUDE.md`, `.claude/skills/`,
  `.claude/agents/`, `.claude/commands/` and (single-repo runs) the
  `.claude/settings.json` hooks and permissions, but no `~/.claude` files and
  no marketplace plugins. The GitHub proxy rejects GraphQL, so `gh pr` and
  `gh issue` fail; use `gh api` REST. Triggers: schedule (one hour minimum),
  API fire, GitHub pull request / issue / release events with filters. No
  "CI failed" trigger and no documented notification channel. Available on
  Pro, Max, Ultra, Team and Enterprise.
- GitHub Free personal account, private repository (verified 2026-11-08):
  Dependabot alerts, security updates and version updates are free but must
  be enabled; secret scanning, push protection and CodeQL need paid add-ons
  that only organizations on Team or Enterprise can buy; branch protection,
  rulesets enforcement, required reviewers and code owners need Pro (about
  $4 a month); Actions includes about $12 of compute a month and 500 MB of
  storage; `gh api /repos/{o}/{r}/dependabot/alerts` works with a token that
  can read Dependabot alerts; the secret-scanning alerts API returns 404 where
  secret scanning isn't enabled.
- Free scanners usable here: gitleaks-action v3 (no license key for personal
  accounts), trufflehog (AGPL), Semgrep CE (LGPL engine, rules licensed for
  internal use; the old `semgrep-action` is archived, run the CLI), zizmor
  (MIT; set `advanced-security: false` on private repositories), osv-scanner
  (Apache 2.0, reusable workflows).
