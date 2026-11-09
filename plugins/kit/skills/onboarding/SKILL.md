---
name: onboarding
description: >
  Set up this computer from scratch with the beep-beginners kit: apps, sign-ins,
  password manager, a private workspace on GitHub shaped by the user's own
  Claude memories, security notices on, and a help line, ending on the first
  exploration. Use when the user says "set me up", "set up my computer", "start
  onboarding", "keep setting me up", "finish setting me up", or pastes the setup
  sentence that mentions beep-beginners. Resumes where it left off.
---

# Onboarding

You take the user from a bare machine to a working setup in one sitting
(D68). They never type a command. Their only jobs are typing passwords,
approving two-factor prompts, pasting their Claude memories, clicking Add in
the Chrome Web Store, and saying Yes to one Windows permission prompt. You do
everything else, and you end by starting on the first thing they want to
figure out. The cloud pieces (the caretaker) are a second sitting: the
`caretaker-setup` chore proposes them at a later session start.

## Rules for every step

- **One sentence first.** Before each step, say in one plain sentence what's
  about to happen and why. Before a permission prompt, also say what it will
  look like.
- **Unslop.** Run the `unslop` skill on every message to the user.
- **Detect, then ask.** Never ask what a script can find out. Ask only about
  accounts, subscriptions, wants, and permission to spend money.
- **Checks use the tool.** A tool counts as working only when its `verify`
  check in `tools.yaml` passes. An installer's exit code doesn't count.
- **Save progress.** After each step, run `state.py done <step>` (or
  `skip <step> --note "<why>"`). If the session ends, the next "keep setting me
  up" continues from `state.py next`.
- **Sign-in pages.** Open the page (in Chrome, with Claude in Chrome when
  connected), tell the user which account and page it is, wait until they
  say they're in, then check it worked. Never ask for, type, read, or store
  a password, recovery code or 2FA code. In automated test runs
  (`BEEP_BEGINNERS_TEST=1`), stop and report the account and page.
- **Money.** Never buy anything without a clear yes to the exact price.
- **Nothing on their accounts without a yes.** The caretaker tasks, the
  GitHub App install and the security settings are each announced in one
  sentence before they happen.
- **Failures.** Retry once if it makes sense. Then explain plainly, skip with
  a note, and move on if later steps don't depend on it. If it blocks
  everything, use the `help-request` skill.

## Scripts

All scripts are Python run through uv:
`uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/<name>.py" ...`

| Script | Use |
| --- | --- |
| `state.py next / done / skip / answer / show` | progress and answers |
| `detect.py` | machine facts, saved into the state |
| `tools.py plan / install-user / write-batch / run-batch / verify` | the software list in `tools.yaml` |
| `pick_folder.py` | the folder picker |
| `workspace.py create / user-settings / git-identity / cloud-ready` | the GitHub workspace |
| `kit.py profile draft / write, security enable, caretaker install, explore new` | the kit (D51) |

If `uv --version` fails, nothing else can run yet. Install uv first with
its own installer, which needs no admin rights:
`powershell -ExecutionPolicy Bypass -c "irm https://astral.sh/uv/install.ps1 | iex"`,
or on macOS and Linux `curl -LsSf https://astral.sh/uv/install.sh | sh`.
Don't use winget for uv: its package pulls in the Visual C++ runtime, which
shows an admin prompt (seen on the test VM, 2026-11-06).
Then refresh PATH: open a new shell, or on Windows prepend
`%LOCALAPPDATA%\Microsoft\WinGet\Links` and `%USERPROFILE%\.local\bin`.

## Steps

Start every session with `state.py next`. If anything was done before, say in
one sentence what's finished and what's next.

### 1. bootstrap

Usually done by the pasted setup sentence, which runs the kit's
`bootstrap.ps1` (see the kit's README). Make sure `claude --version`,
`git --version` and `uv --version` all work. Nothing in this step may show
an admin prompt. If something is missing, run the bootstrap again:
`irm https://raw.githubusercontent.com/kriegcloud/beep-beginners/main/bootstrap.ps1 | iex`.
It skips what's already installed. Don't install Git with winget here: Git's
regular installer asks for admin even with `--scope user` (seen on the test
VM, 2026-11-06). The bootstrap uses the portable build instead.

### 2. detect

Run `detect.py`. Don't read the whole output to the user. Summarize in two or
three sentences: the Windows edition, how many of the tools are already there,
and anything worth flagging (Documents synced by OneDrive, Bitwarden found).

### 3. chrome (Claude in Chrome first)

Every later browser step depends on this.

1. If Chrome is missing, run `tools.py install-user --only chrome`.
2. Check `facts.claude_in_chrome` from step 2: it is true only when the
   extension is installed in this computer's Chrome. If it is false, the
   extension is missing here, even if a Claude in Chrome tool answers: the
   tool can reach a Chrome on another computer signed in to the same Claude
   account (seen on the test VM, 2026-11-07). Go to 3.
   If it is true, call a Claude in Chrome tool, such as listing tabs. If it
   works, this step is done.
3. If it doesn't, open the Web Store page in Chrome, starting Chrome with
   `--no-first-run --no-default-browser-check` so its own welcome screens
   don't get in the way (seen on the test VM):
   `https://chromewebstore.google.com/detail/claude/fcoeoabgfenejglbffodgkkbkcdhcgfn`.
   Tell the user to click **Add to Chrome**, then **Add extension**, then
   sign in to Claude in the extension with the same account as this app.
4. Wait, then test the connection again. If it still fails, ask them to make
   sure Chrome is open, then try once more.

### 4. questions

Ask one AskUserQuestion round, recommended answer first:

- What should I call you? (`answer name`)
- Which AI subscriptions do you pay for? Claude, ChatGPT, Grok, Gemini.
  This is multi-select. (`answer subscriptions --list claude,chatgpt`)
- Which Claude plan is it? Pro, Max 5x, Max 20x, or not sure. No machine can
  tell, and the caretaker needs Max (D66). (`answer claude_plan max5|max20|pro|unsure`)
- Which accounts do you already have? GitHub, 1Password, Bitwarden, Tailscale,
  Microsoft (OneDrive). This is multi-select. Keep every option even when
  detection found no app: a Bitwarden web-vault user has nothing installed.
  (`answer accounts --list github,bitwarden`)
- Who helps you when something on this computer breaks? Their first name,
  and whether they may fix things from their own computer, only over a
  private Tailscale link, only with their own key, and only when you ask.
  Recommend yes. (`answer helper_name "<name>"`, `answer helper_access true|false`)
  This yes is the user's consent for the help line in step 7. Without it,
  leave `--keys-url` out there. The helper's public keys come from GitHub:
  ask for the helper's GitHub username and save
  `answer helper_keys_url https://github.com/<username>.keys`.

Then, if they don't have 1Password: "1Password is $35.88 for the first year,
then $47.88 a year after that. OK to sign up?" Only a clear yes moves on. The
user does the payment form. (`answer onepassword_purchase true`)

### 5. profile (their memories, then five or six questions)

This is what makes the workspace theirs (D55).

1. Say in two sentences: "Claude keeps memories about how you work. If you
   paste them here, I can set your workspace up around them, and I'll only
   ask what they don't already cover." Tell them where to find them: in the
   Claude app, Settings, then Memory, select all and copy. In test runs
   (`BEEP_BEGINNERS_TEST=1`) read the file named in
   `BEEP_BEGINNERS_MEMORIES_FIXTURE` instead.
2. Save the paste to a file outside the workspace
   (`%USERPROFILE%\.beep-beginners\memories.txt`) and run
   `kit.py profile draft <that file>`. It returns the entries by section, the
   six interview questions with what the memories already answer, and an
   `answers_template`. Never put the raw memories into the workspace.
3. Ask only the questions marked not answered, in one AskUserQuestion round
   of at most five or six: what they do, what they want to build or figure
   out first, how they like to be helped, what helps a new idea land,
   which AI subscriptions (skip if step 4 answered it), who helps them (skip
   if step 4 answered it). Recommended answers come from the memories.
4. Write the answers JSON (the template's shape): `name`, `about` (one
   paragraph in the third person, their background, what they're learning,
   what they want to figure out first), `how_i_learn` (three to five lines),
   `folders` (one per business or recurring activity the memories show, each
   with a `name`, a one-line `summary` and an `agents` text with the rules
   for that folder), `helper`, `subscriptions`, `skills`, `first_exploration`.
5. **Skills.** For each recurring routine in the memories (a listing
   process, a morning routine, a reporting habit), write a personal skill:
   `name` (lowercase words with hyphens), `description` (when to use it, with
   the phrases they'd say), `body` (the steps, the rules, what never to do
   without asking). The worked example in `${CLAUDE_PLUGIN_ROOT}/examples/profile-card-reseller/`
   shows the shape for a card reseller with a job hunt: read `answers.json`
   there before writing yours. Run `unslop` on every text.
6. Show the user the `about` paragraph and the skill names in plain words
   ("I'll give you two helpers: one that drafts card listings, one that runs
   your morning job hunt") and fix anything they correct. Save the file as
   `%USERPROFILE%\.beep-beginners\profile-answers.json` and
   `answer profile_answers "<that path>"`, `answer first_exploration "<their words>"`.

### 6. install-user

Run `tools.py plan`. Tell the user in one or two sentences how many apps are
already there, how many you'll install, and that this part needs no
permission. Then run `tools.py install-user`. The output has a `detect_after`
section. Report anything that failed, in plain words. gitleaks is on the list
now: say in one sentence that it checks files for passwords before anything
is saved.

OpenKnowledge can make itself the default app for `.md` files. Say so in one
sentence before installing it.

### 7. install-machine (one Windows permission prompt)

Windows only. Run `tools.py write-batch --keys-url <helper_keys_url>`.
Leave out `--keys-url` when `helper_access` isn't true. The batch holds the
machine-wide installs (Tailscale, Visual Studio Build Tools, PowerShell 7) and
the help-line setup for SSH (decision 22).

Run the batch yourself; never ask the user to type or paste a command. Read
the generated `.ps1` first and say in one sentence what it changes. If it
includes the help line, cite the user's step 4 yes (`helper_access`), since
that answer is their consent. Then tell the user: "Windows will ask once
whether to allow changes. Click Yes. A few things install in the background;
Build Tools is a large download and can take 10 to 20 minutes." Then run
`tools.py run-batch`. The Yes click is the user's only part. Windows cancels
the prompt by itself after about two minutes if nobody clicks, so say it's
coming right before you run the batch, not earlier. If it reports
`ran: false`, the prompt was declined or timed out: ask whether to try again.

On macOS and Linux, install the remaining tools one at a time with the
user's OK. Each may ask for the computer password.

### 8. signin-github

1. Run `gh auth login --web --hostname github.com --git-protocol https --scopes admin:public_key,workflow,repo`.
   `workflow` is needed to push the workspace's checks; `repo` covers the
   `kit/review` commit status (D70: GitHub lets only GitHub Apps create check
   runs, so the kit's review verdict is a commit status, which this token may
   post). One login, every scope (D39). Test runs add the
   scopes in `BEEP_BEGINNERS_GH_EXTRA_SCOPES` (comma-separated), such as
   `delete_repo`, so the test reset can remove its repos.
   It prints a one-time code and opens github.com/login/device. If the user
   has no GitHub account, open github.com/signup first.
2. Tell the user it's the GitHub sign-in page. With Claude in Chrome, type the
   one-time code into the device page for them (a device code isn't a secret),
   and let them sign in and click Authorize.
3. Check: `gh api user --jq .login`. Then run `gh auth setup-git`, so git
   pushes use this sign-in.
4. Run `workspace.py git-identity --name "<name>"`.

### 9. signin-claude-cli

Run `claude auth login`. It opens the Claude sign-in page. Tell the user to
use the same account as this desktop app. Check with `claude auth status`
that `loggedIn` is true, and that the email is the same account the desktop
app uses. Compare the two silently; never show the email in evidence.

### 10. signin-1password

1. If there's no account, open https://1password.com/sign-up/ (Individual).
   The user signs up and pays, but only after step 4's yes.
   If the Microsoft Store edition of 1Password is installed (an app package
   named `DC5C6510.2032887045529`), say in one sentence that it can't work
   with the command-line tool, and that step 6 installed the 1password.com
   edition next to it; the user signs in to that one. The Store edition can
   be removed later.
2. Open the 1Password app: on Windows `Start-Process onepassword://` (the
   scheme is `onepassword`, not `1password`; the Store build has no exe on
   PATH), on macOS `open -a 1Password`. The user signs in.
3. Turn on Settings > Developer > "Integrate with 1Password CLI". Tell the
   user exactly where the switch is and wait. It needs Windows Hello.
   When 1Password shows "Pick your preferred way to unlock", tell the user
   to choose **Balanced** and Update settings. Strict makes every `op` call
   ask for Authorize and Windows Hello again (test VM, 2026-11-07).
4. Check with `op vault list`, never `op whoami` alone: the vault listing is
   what makes 1Password show its "Access Requested" dialog, while `op whoami`
   on its own only says "account is not signed in". Say first that 1Password
   will ask to allow access and then ask for Windows Hello. The first time it
   asks for the account password instead, and it gives up after about a
   minute, so ask the user to stay by the screen. Windows Hello must be set
   up (Settings > Accounts > Sign-in options > PIN) or the dialog never
   appears; `detect.py` reports `windows_hello`. Each program that calls
   `op` (PowerShell, cmd, uv) is approved once. Then create the agents' vault,
   unless `op vault list` already shows it: `op vault create <vault>`, where
   `<vault>` is `BEEP_BEGINNERS_AGENTS_VAULT` if set, otherwise `Agents`. Test
   runs set it to their test vault, so they never write to a real vault.

### 11. passwords (Bitwarden to 1Password)

Only if they use Bitwarden. In tests (`BEEP_BEGINNERS_TEST=1`), import the
fixture named in `BEEP_BEGINNERS_BITWARDEN_FIXTURE` into the vault named in
`BEEP_BEGINNERS_IMPORT_VAULT` instead, and skip the Bitwarden export.

1. In Chrome, open the Bitwarden web vault > Tools > Export vault. Choose
   **.json (Encrypted)** and **Password protected**. The user types a new
   export password twice and confirms with their master password.
   Unencrypted JSON won't import.
2. Open 1Password.com > Import > Bitwarden, upload the downloaded file, and
   let the user type the export password.
3. Check the item count 1Password reports against the export's count, which
   Bitwarden shows. Report both numbers.
4. Delete the export file from Downloads. Tell the user that Bitwarden stays
   as it was until they choose to close the account.

### 12. github-key

Create an SSH key in 1Password (`op item create --category "SSH Key"
--title "GitHub <computer name>" --vault <vault> --ssh-generate-key ed25519`),
where `<vault>` is `BEEP_BEGINNERS_KEY_VAULT` if set, otherwise `Private`,
then add its public key to GitHub (`gh ssh-key add` with the public key from
`op item get <id> --fields "public key"`). Show nothing but the key's title.
Pushes keep using HTTPS through `gh auth setup-git`, so a backup never waits
for a 1Password prompt (decision D33).

### 13. location

Run `pick_folder.py --default <facts.default_workspace>`. Before it opens,
say: "A folder picker is opening. The suggested folder is fine; click OK."
If it reports `onedrive: true`, read out the warning and run it again. On
`no-dialog`, ask in chat with the default as the recommended answer.
Save the answer: `answer workspace_parent "<path>"`.

### 14. workspace

1. Say: "I'm making your private workspace on GitHub now, shaped by your
   profile, and turning on GitHub's free security notices for it."
2. Run `workspace.py create --parent "<path>" --answers "<profile_answers path>" --user-name "<name>"`.
   It copies the template, writes your profile into `AGENTS.md` and your
   personal skills into `.claude/skills/`, creates the private repo on
   GitHub, pushes, installs the plugins at project scope, and turns on
   Dependabot alerts, security updates and delete-branch-on-merge
   (`kit security enable`). Report the `security` part in one sentence.
3. If the memories or answers named scripts in Documents (a lister, an
   import script), ask: "Copy your scripts from Documents into your
   workspace, so they're backed up and versioned? Your data files stay where
   they are." On yes, run the `project` skill's
   `kit project new <name> --stack python --from "<folder>" --summary "..."`
   from the workspace, then `kit land --message "Bring in the scripts from Documents"`.
4. Run `workspace.py user-settings`. This makes auto mode the default
   permission mode (decision D24) and pins Opus 5.5 at medium effort (D40).
5. Backups of Documents data: if `facts.onedrive_signed_in` is false, ask
   whether they have a Microsoft account. If they do, open OneDrive so they
   can sign in and turn on Documents backup. If not, skip with a note.

### 15. The cloud pieces come later (D68)

Nothing to do in this sitting. The Claude GitHub App, the claude.ai cloud
setup and the three caretaker tasks are the `caretaker-setup` skill, which
the kit proposes at the start of a later session ("Ten minutes to set up your
caretaker?"). Until then, session start does the upkeep: kit updates,
finished work that passed its checks, the index, the backup check. Mention
this in one sentence when you reach the welcome.

### 16. signin-tailscale

Run `tailscale up --unattended` (Windows: the full path
`C:\Program Files\Tailscale\tailscale.exe`). It prints a login URL. Open it,
and tell the user it's the Tailscale sign-in page. They can sign up with
their GitHub account. Check with the `tailscale` verify in `tools.yaml`.

### 17. remote-help

1. The help line was set up in step 7: SSH only from Tailscale addresses,
   only the helper's keys, password logins off. Confirm with
   `remote_access.py status` from the helper plugin, or with the `verify` row
   for `openssh-server`.
2. In Chrome, open https://login.tailscale.com/admin/machines, find this
   computer, choose **Share...**, and create an invite link. Tell the user to
   text that link to their helper. Never send it anywhere yourself.
3. Tell the user, in one or two sentences, that the helper connects only when
   asked, and that "stop <helper>'s access" turns it off.

### 18. other-ai

Only for subscriptions other than Claude. The tools were installed in step 6.
For each one, open its sign-in (`codex login`, `grok` first run, `gemini`
first run) and wait for the user. CLIProxyAPI runs at logon as a scheduled
task. Its own sign-in for each vendor uses the same accounts. The workspace
`AGENTS.md` already explains when agents route work through it.

### 19. verify

Run `tools.py verify --evidence "<workspace>/docs/setup-check.json"`. Every
row should be `ok: true`. Fix what you can and run it again. Report what's
left in one short list. Save the evidence file with
`kit land --message "Record the setup check"` from the workspace, then
`kit sync --at end` so it is backed up.

### 20. first-exploration (the hand-off, D57)

Write a short welcome (about 120 words, through `unslop`) and save it as
`docs/WELCOME.md` in the workspace. It covers: to start work, open the Claude
app, choose Code, and pick the workspace folder (give the path); things to
say ("I want to explore ...", "build me ...", "what needs me?", "teach me
what you just did", "I need help", "stop <helper>'s access"); the four
commands to type (`/grill-me`, `/teach`, `/handoff`, `/wait-what`); that
everything saves to GitHub by itself; and one line on the caretaker: on Max,
that it can be set up next time in ten minutes, runs on their Claude account
while they're away, and can be paused by saying "pause my caretaker"; on Pro,
that the kit does that upkeep whenever they open Claude here, and what
upgrading unlocks.

Then don't stop there. Say: "Let's start on the thing you said you wanted to
figure out: <first_exploration>." Invoke the `explore` skill with
`--root "<workspace>"` on every kit command, and run its notes stage with what
the memories and the interview already said, then as far into research as one
session allows. End with `kit land` and `kit sync --at end` from the
workspace, `state.py done first-exploration`, and one line: "That's saved and
backed up. Next time, open Claude on your workspace folder and we pick up
from the next question."
