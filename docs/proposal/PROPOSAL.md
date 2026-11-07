# Phase 3 proposal: tree, plugins, tools, onboarding flow

Status: waiting for approval (2026-11-06). Read with `docs/DECISIONS.md`
(D24 to D32) and the draft `docs/proposal/tools.yaml`.

## 1. Repository tree (kriegcloud/beep-beginners, public)

```text
beep-beginners/
  .claude-plugin/marketplace.json   marketplace "beep-beginners"; every plugin by relative path
  plugins/
    onboarding/                     one-time setup, resumable
      .claude-plugin/plugin.json
      skills/onboarding/SKILL.md    the runbook: steps, one-sentence explanations, stop/resume
      tools.yaml                    the software manifest (decision 11)
      scripts/                      Python, `uv run --script`, PEP 723 metadata
        detect.py                   machine facts -> JSON (OS, edition, WSL, OneDrive redirection,
                                    tools + versions, git identity, SSH keys, gh auth, password
                                    managers, user name, paths)
        tools.py                    detect | plan | install-user | write-elevated-batch | verify,
                                    all from tools.yaml; verify writes evidence JSON
        pick_folder.py              native folder picker (FolderBrowserDialog / osascript /
                                    zenity|kdialog), BEEP_BEGINNERS_WORKSPACE override
        state.py                    resumable state in ${CLAUDE_PLUGIN_DATA}/onboarding.json
        workspace.py                create the private repo from template/, clone, write
                                    workspace.config, seed folder pairs, set user settings
        remote_help.py              OpenSSH key + Tailscale-only firewall rule (elevated part
                                    goes in the batch), share invite, on/off switch
      elevated/batch.ps1.tmpl       the single elevated session (one UAC prompt)
      seeds/                        per-person folder rules, applied only when chosen (see Q2)
    guards/                         safety hooks, on in every workspace
      .claude-plugin/plugin.json
      hooks/hooks.json              exec form: uv run --script ${CLAUDE_PLUGIN_ROOT}/hooks/x.py
      hooks/git_guard.py            PreToolUse Bash|PowerShell: Pocock list + force push +
                                    push to non-origin; exit 2
      hooks/secret_guard.py         PreToolUse Read|Edit|Write|Bash|PowerShell|Grep|Glob:
                                    .env, *.pem, id_*, secrets paths; backslash-normalized
      hooks/session_start.py        "guards on" banner; catch-up push; HELP-REQUEST reminder
      hooks/session_end.py          commit-nothing push to origin with timeout; regenerate
                                    CHANGELOG-FOR-ED.md from commit subjects
      tests/                        pytest cases for every guard decision
    explore/                        explorations -> goals, plain-language packets
      skills/explore/SKILL.md       triggered by "I want to explore/figure out X"
      skills/goal/SKILL.md          graduate a packet into goals/<slug>/ and work it
      templates/exploration/ templates/goal/
      scripts/packet.py             bookkeeping: manifest, status, index (agents only)
    unslop/                         skills/unslop/SKILL.md (from beep-effect, unchanged rules)
    helper/                         help path and remote access switch
      skills/help-request/          writes HELP-REQUEST.md, tells the user to text the helper
      skills/helper-access/         "stop/start <helper>'s access" (sshd + firewall + share)
      skills/teach-back/            "teach me what you just did"
    pokeseller/                     resale tools, enabled only in the PokeSeller folder
      skills/mercari-listing/       how to fill a Mercari listing in Claude in Chrome
      hooks/listing_check.py        PostToolUse Write|Edit on listing drafts: checks the
                                    folder's listing-rules.yaml (Japanese characters, cert
                                    numbers, condition, shipping line, empty price)
    job-hunt/                       skills/morning-job-hunt/ (search, tailor resume, tracker)
  template/                         the thin template onboarding copies into the new repo
    AGENTS.md  CLAUDE.md (@AGENTS.md)  .gitignore  .claude/settings.json
    explorations/README.md  goals/README.md  docs/README.md
  tests/
    vm/run.sh                       lock + calls beep-effect's ops/vm scripts, never copies them
    vm/evidence.sh                  verify every tools.yaml entry, gh auth, extension, sign-ins
    vm/baseline/                    winget inventories of the start snapshot
    vm/fixtures/                    fake Bitwarden encrypted export (D31)
  docs/DECISIONS.md  docs/research/  docs/MAINTAINING.md
  README.md                         two screens for the user: the one sentence, the commands
  LICENSE
```

## 2. Plugins

| Plugin | On by default | Ed-facing entry | Notes |
| --- | --- | --- | --- |
| onboarding | user scope, once | the pasted sentence; "finish setting me up" | removed from enabled list when done |
| guards | every workspace | none (banner only) | D24, D25, decision 17 |
| explore | every workspace | "I want to explore X" | decision 18-style plain packets |
| unslop | every workspace | none | agents run it on all user-facing text |
| helper | every workspace | "I need help", "stop Benjamin's access" | decisions 22, 23 |
| pokeseller | PokeSeller folder | "list this card on Mercari" | `enabledPlugins` in that folder's settings |
| job-hunt | job-hunt folder | "do my morning job hunt" | replaces the cloud routine that suspends when the PC is off |
| mattpocock-skills@claude-plugins-official | every workspace | `/grill-me`, `/teach`, `/handoff`, `/wait-what` | D30 |

## 3. Workspace that onboarding creates (private, on the user's GitHub)

```text
Workspace/                (default C:\Users\<user>\Workspace\, outside OneDrive)
  <name>-workspace/       AGENTS.md CLAUDE.md .claude/settings.json workspace.config
                          CHANGELOG-FOR-ED.md explorations/ goals/ docs/
                          job-hunt/{AGENTS.md,CLAUDE.md}  duffers/{...}  PokeSeller/{...}
  PokeLedger/             its own private repo; AGENTS.md says mentor mode
```

`workspace.config` holds paths only (Documents data folders, card inbox, resume
folder). Raw data and the workbook stay in Documents with OneDrive as backup
(decision 5).

## 4. Onboarding flow

Every step announces itself in one sentence, records progress in `state.py`,
and can be resumed with "keep setting me up".

| # | Step | Machine does | User does |
| --- | --- | --- | --- |
| 0 | Bootstrap (D26) | install CLI, add marketplace, install onboarding | pastes one sentence |
| 1 | Detect | `detect.py` | nothing |
| 2 | Claude in Chrome | install Chrome if missing, open the Web Store page, wait, test the connection | clicks Add |
| 3 | Questions | one round: accounts held, AI subscriptions, wants, OK to buy 1Password ($36 first year, then $48) | answers |
| 4 | User-scope installs | `tools.py install-user` | nothing |
| 5 | One UAC prompt | explain, then run the elevated batch: Tailscale, VS Build Tools, PowerShell 7, OpenSSH + firewall | clicks Yes once |
| 6 | Sign-ins | open each page in Chrome and wait: GitHub (`gh auth login --web`), Claude CLI, 1Password, Tailscale | signs in, 2FA |
| 7 | 1Password | enable CLI integration, create Agents vault, Bitwarden encrypted export, then import | master password, Windows Hello |
| 8 | GitHub key | 1Password SSH key, added to GitHub through Chrome; git identity | approves |
| 9 | Location | folder picker at `%USERPROFILE%\Workspace`, OneDrive warning | picks a folder |
| 10 | Workspace | private repo from `template/`, clone, seeds, PokeLedger repo, OneDrive on for Documents data, auto mode in user settings | nothing |
| 11 | Remote help | Tailscale share invite to the helper, key, firewall | approves the share |
| 12 | Other AI | if subscribed: vendor app/CLI, CLIProxyAPI task, AGENTS.md routing line | signs in |
| 13 | Verify | `tools.py verify` for every tool, evidence JSON, welcome message naming `/grill-me` and `/teach` | reads it |

## 5. Questions for approval

1. **Template shape.** Proposed: a `template/` folder that onboarding copies into
   a new private repo with `gh repo create --private`. If the whole repository were
   marked as a GitHub template instead, every workspace would also get a copy of
   `plugins/`, and the template is supposed to be thin. With this option the repo
   never needs the template flag.
2. **Where the user's own rules live.** Proposed: `plugins/onboarding/seeds/milkman/`
   holds his Mercari rules, job-hunt steps and PokeLedger conventions, with names,
   places, money amounts, account and trigger ids, and buyer details scrubbed out.
   Onboarding copies it into his private workspace only when he confirms it's him.
   The alternative keeps the kit with no seeds at all: onboarding reads his
   memories from claude.ai through Claude in Chrome and writes the folder rules
   from them. That keeps the most out of the public repo, but the VM proof can't
   reproduce it, because the VM is signed in as you.
3. **Node through fnm instead of nvm-windows.** nvm-windows asks for admin and
   needs symlink rights. fnm is portable and user-scope, so Node never adds a
   UAC prompt.
4. **Helper's name in public files.** Proposed: use "Benjamin" only in seeds and in
   `workspace.config` (`helper_name`). Kit text says "your helper".
