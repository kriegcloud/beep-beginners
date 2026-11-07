---
name: onboarding
description: >
  Set up this computer from scratch with the beep-beginners kit: apps, sign-ins,
  password manager, a private workspace on GitHub, and a help line. Use when
  the user says "set me up", "set up my computer", "start onboarding", "keep
  setting me up", "finish setting me up", or pastes the setup sentence that
  mentions beep-beginners. Resumes where it left off.
---

# Onboarding

You take the user from a bare machine to a working setup. They never type a
command. Their only jobs are typing passwords, approving two-factor prompts,
clicking Add in the Chrome Web Store, and saying Yes to one Windows permission
prompt. You do everything else.

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
| `workspace.py create / move-code / user-settings / git-identity` | the GitHub workspace |

If `uv --version` fails, nothing else can run yet. Install uv first with
`winget install --id astral-sh.uv -e --source winget --accept-package-agreements --accept-source-agreements --disable-interactivity`,
or on macOS and Linux with `curl -LsSf https://astral.sh/uv/install.sh | sh`.
Then refresh PATH: open a new shell, or on Windows prepend
`%LOCALAPPDATA%\Microsoft\WinGet\Links` and `%USERPROFILE%\.local\bin`.

## Steps

Start every session with `state.py next`. If anything was done before, say in
one sentence what's finished and what's next.

### 1. bootstrap

Usually done by the pasted setup sentence (see the kit's README). Make sure
`claude --version`, `git --version` and `uv --version` all work. Install git
with `winget install --id Git.Git -e --scope user ...` if needed.

### 2. detect

Run `detect.py`. Don't read the whole output to the user. Summarize in two or
three sentences: the Windows edition, how many of the tools are already there,
and anything worth flagging (Documents synced by OneDrive, Bitwarden found).

### 3. chrome (Claude in Chrome first)

Every later browser step depends on this.

1. If Chrome is missing, run `tools.py install-user --only chrome`.
2. Test the connection: call a Claude in Chrome tool, such as listing tabs.
   If it works, this step is done.
3. If it doesn't, open the Web Store page in Chrome:
   `https://chromewebstore.google.com/detail/claude/fcoeoabgfenejglbffodgkkbkcdhcgfn`.
   Tell the user to click **Add to Chrome**, then **Add extension**, then
   sign in to Claude in the extension with the same account as this app.
4. Wait, then test the connection again. If it still fails, ask them to make
   sure Chrome is open, then try once more.

### 4. questions

Ask one AskUserQuestion round, recommended answer first:

- What should I call you? (`answer name`)
- Which AI subscriptions do you pay for? Claude, ChatGPT, Grok, Gemini.
  This is multi-select. (`answer subscriptions '["claude",...]'`)
- Which accounts do you already have? GitHub, 1Password, Bitwarden, Tailscale,
  Microsoft (OneDrive). This is multi-select. (`answer accounts '[...]'`)
- If the kit has a seed for this person (`seeds/<id>/seed.toml`), confirm it's
  them by its description. (`answer seed '"milkman"'`)

Then, if they don't have 1Password: "1Password is $35.88 for the first year,
then $47.88 a year after that. OK to sign up?" Only a clear yes moves on. The
user does the payment form. (`answer onepassword_purchase true`)

### 5. install-user

Run `tools.py plan`. Tell the user in one or two sentences how many apps are
already there, how many you'll install, and that this part needs no
permission. Then run `tools.py install-user`. The output has a `detect_after`
section. Report anything that failed, in plain words.

OpenKnowledge can make itself the default app for `.md` files. Say so in one
sentence before installing it.

### 6. install-machine (one Windows permission prompt)

Windows only. Run `tools.py write-batch --keys-url <seed helper.keys_url>`.
Leave out `--keys-url` when there's no seed. The batch holds the
machine-wide installs (Tailscale, Visual Studio Build Tools, PowerShell 7) and
the help-line setup for SSH (decision 22).

Tell the user: "Windows will ask once whether to allow changes. Click Yes. A
few things install in the background; Build Tools is a large download and
can take 10 to 20 minutes." Then run `tools.py run-batch`. If it reports
`ran: false`, the prompt was declined: ask whether to try again.

On macOS and Linux, install the remaining tools one at a time with the
user's OK. Each may ask for the computer password.

### 7. signin-github

1. Run `gh auth login --web --hostname github.com --git-protocol https`.
   It prints a one-time code and opens github.com/login/device. If the user
   has no GitHub account, open github.com/signup first.
2. Tell the user it's the GitHub sign-in page. With Claude in Chrome, type the
   one-time code into the device page for them (a device code isn't a secret),
   and let them sign in and click Authorize.
3. Check: `gh api user --jq .login`. Then run `gh auth setup-git`, so git
   pushes use this sign-in.
4. Run `workspace.py git-identity --name "<name>"`.

### 8. signin-claude-cli

Run `claude auth login`. It opens the Claude sign-in page. Tell the user to
use the same account as this desktop app. Check with `claude auth status`
that `loggedIn` is true, and that the email is the same account the desktop
app uses. Compare the two silently; never show the email in evidence.

### 9. signin-1password

1. If there's no account, open https://1password.com/sign-up/ (Individual).
   The user signs up and pays, but only after step 4's yes.
2. Open the 1Password app. The user signs in.
3. Turn on Settings > Developer > "Integrate with 1Password CLI". Tell the
   user exactly where the switch is and wait. It needs Windows Hello.
4. Check with `op whoami` (it may show a Windows Hello prompt; say so
   first). Then create the agents' vault, unless `op vault list` already
   shows it: `op vault create <vault>`, where `<vault>` is
   `BEEP_BEGINNERS_AGENTS_VAULT` if set, otherwise `Agents`. Test runs set it
   to their test vault, so they never write to a real vault.

### 10. passwords (Bitwarden to 1Password)

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

### 11. github-key

Create an SSH key in 1Password (`op item create --category "SSH Key"
--title "GitHub <computer name>" --vault <vault> --ssh-generate-key ed25519`),
where `<vault>` is `BEEP_BEGINNERS_KEY_VAULT` if set, otherwise `Private`,
then add its public key to GitHub (`gh ssh-key add` with the public key from
`op item get <id> --fields "public key"`). Show nothing but the key's title.
Pushes keep using HTTPS through `gh auth setup-git`, so a backup never waits
for a 1Password prompt (decision D33).

### 12. location

Run `pick_folder.py --default <facts.default_workspace>`. Before it opens,
say: "A folder picker is opening. The suggested folder is fine; click OK."
If it reports `onedrive: true`, read out the warning and run it again. On
`no-dialog`, ask in chat with the default as the recommended answer.
Save the answer: `answer workspace_parent '"<path>"'`.

### 13. workspace

1. Run `workspace.py create --parent "<path>" --seed <seed or omit> --user-name "<name>"`.
   It copies the template, applies the seed, writes `workspace.config`,
   creates the private repos on GitHub, and pushes.
2. If the seed has `move_code` and those Documents folders exist, ask: "Copy
   your scripts from Documents into your workspace, so they're backed up and
   versioned? Your data files stay where they are." On yes, run
   `workspace.py move-code --seed <seed>`.
3. Run `workspace.py user-settings`. This makes auto mode the default
   permission mode (decision D24).
4. Backups of Documents data: if `facts.onedrive_signed_in` is false, ask
   whether they have a Microsoft account. If they do, open OneDrive so they
   can sign in and turn on Documents backup. If not, skip with a note.

### 14. signin-tailscale

Run `tailscale up --unattended` (Windows: the full path
`C:\Program Files\Tailscale\tailscale.exe`). It prints a login URL. Open it,
and tell the user it's the Tailscale sign-in page. They can sign up with
their GitHub account. Check with the `tailscale` verify in `tools.yaml`.

### 15. remote-help

1. The help line was set up in step 6: SSH only from Tailscale addresses,
   only the helper's keys, password logins off. Confirm with
   `remote_access.py status` from the helper plugin, or with the `verify` row
   for `openssh-server`.
2. In Chrome, open https://login.tailscale.com/admin/machines, find this
   computer, choose **Share...**, and create an invite link. Tell the user to
   text that link to their helper. Never send it anywhere yourself.
3. Tell the user, in one or two sentences, that the helper connects only when
   asked, and that "stop <helper>'s access" turns it off.

### 16. other-ai

Only for subscriptions other than Claude. The tools were installed in step 5.
For each one, open its sign-in (`codex login`, `grok` first run, `gemini`
first run) and wait for the user. CLIProxyAPI runs at logon as a scheduled
task. Its own sign-in for each vendor uses the same accounts. The workspace
`AGENTS.md` already explains when agents route work through it.

### 17. verify

Run `tools.py verify --evidence "<workspace>/docs/setup-check.json"`. Every
row should be `ok: true`. Fix what you can and run it again. Report what's
left in one short list. Commit the evidence file
("Record the setup check").

### 18. welcome

Write a short welcome (about 120 words, through `unslop`) and save it as
`docs/WELCOME.md` in the workspace. It covers:

- To start work, open the Claude app, choose Code, and pick the workspace
  folder (give the path).
- Things to say: "I want to explore ...", "teach me what you just did",
  "I need help", "stop <helper>'s access".
- Commands to type: `/grill-me` to stress-test a plan, `/teach` for a lesson.
- Everything saves to GitHub by itself at the end of each session.

Show it to the user, then run `state.py done welcome`.
