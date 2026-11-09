---
name: caretaker-setup
description: >
  The second sitting (D68, D76): set up the caretaker that tidies the
  workspace while the user is away, with the agent doing every step itself.
  Use when the caretaker-setup chore asks "Ten minutes to set up your
  caretaker?" and the user says yes, or when the user says "set up my
  caretaker", "turn on the caretaker", or asks why nothing happens while
  they're away. Needs a Max plan; on Pro, explain what upgrading unlocks.
---

# Caretaker setup

Three cloud tasks run on the user's own Claude account: a morning sweep, a
run whenever finished work is waiting to be checked, and a weekly gardener on
Sunday night. They use the user's subscription (D66), so this is their call.
The user has no idea what a GitHub App or a routine is and never needs to:
you do every step, say one plain sentence before each, and ask only yes/no
questions (D76). A click that truly needs a human (a GitHub two-factor
prompt, a confirm button the browser extension can't press) gets exact words
on what to click and why, and goes into NEEDS-YOU.md until it's done.

Say first, in two sentences: "The caretaker runs on your Claude account while
you're away: it merges finished work that passed its checks, reads security
notices, and tidies your notes once a week. It uses a little of your Claude
each day, and you can pause it any time by saying 'pause my caretaker'."

## Plan check (D66)

The plan is in `.kit/profile.json` (`plan`) or the onboarding answers
(`claude_plan`). If it isn't Max 5x or higher, stop here and say: "The
caretaker needs a Max plan, because cloud tasks draw from the same usage pool
as your own sessions and stop at the limit. On Pro, the kit does the same
upkeep whenever you open Claude here: finished work that passed its checks
goes into the main copy at the start of your session. If you upgrade later,
say 'set up my caretaker'." Record it: `kit caretaker record --plan pro`.

## Glossary first

Add the two terms the steps use, so the user can look them up later:

```
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/kit.py" glossary add "GitHub App" --meaning "A permission slip on GitHub that lets Claude's cloud helper read your workspace and open or merge finished work. You can take it back any time on GitHub."
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/kit.py" glossary add "Routine" --meaning "A task Claude runs on its own schedule in the cloud, on your account, without you opening the app. The caretaker is three routines."
```

## Step 1: the GitHub App (the agent drives Chrome)

Say: "GitHub needs a permission slip so Claude's cloud helper can read your
workspace. I'll set it up; you may see a GitHub page asking you to confirm."

1. With Claude in Chrome (installed in onboarding), open
   https://github.com/apps/claude in the user's Chrome, which is signed in to
   their GitHub account. Click **Install** (or **Configure** if it's already
   installed). If GitHub shows an account picker, choose the user's own
   account. On the permissions page choose **Only select repositories** and
   pick the workspace repository, then **Install**.
2. GitHub may ask the user to confirm their password or a two-factor code.
   Never type those. Say: "GitHub wants you to confirm it's you: type your
   password (or the code from your phone) on this page, then I'll carry on."
   Wait for them.
3. GitHub sends the browser to claude.ai to finish. If a **Finish connecting
   GitHub** button appears, click it; the user must already be signed in to
   claude.ai in Chrome as the same account as this app. If claude.ai asks
   them to sign in, say: "This is the Claude sign-in page; sign in with the
   same account you use here, then I'll continue."
4. Check: `gh api repos/<owner>/<repo>/installation` returns 200 when the
   App covers the workspace. Save `state.py answer github_app true`. If it
   still returns 404 after one retry, add a NEEDS-YOU item with the exact
   click to make (`kit needs-you add --title "Finish the GitHub permission slip" ...`)
   and stop this skill; it resumes next time.

## Step 2: the cloud setup on claude.ai (usually already done)

Open https://claude.ai/code in the user's Chrome. If it shows a GitHub connect
step or offers to make a first environment ("Default"), accept both on the
user's behalf; say "Claude needs a workspace of its own in the cloud; I'm
making it now." If it opens straight to the session list, it's done.

## Step 3: the three routines (the agent creates them)

1. Run `workspace.py cloud-ready` for the workspace URL and the UTC cron for
   7:07 local, then
   `kit caretaker install --workspace <url> --environment <env id> --cron-utc "<cron>" --garden-cron-utc "<Sunday 21:07 local, in UTC>" --ref stable`.
   The environment id is the account's Default cloud environment (the
   `schedule` skill lists them). The route is the kit as the task's second
   repository (D45 as amended: the only route that runs in the cloud).
2. Invoke the `schedule` skill. Create `sweep`, then `pr_opened`, then
   `garden`, each with the schedule tool's create action and the body as
   given (two sources, Opus 5.5, no connectors). Then `create_webhook_trigger`
   with the webhook spec and `pr_opened`'s id for `pull_request.opened` on
   the workspace repository.
   If the create answers `repo_access_denied`, Step 1 didn't finish: go back
   to it.
3. Record: `kit caretaker record --sweep <id> --pr <id> --garden <id> --plan max5`,
   then `kit land --message "Set up the caretaker"` and `kit sync --at end`.
4. Say in two sentences what will happen: "Every morning around seven the
   caretaker checks your workspace, and on Sunday nights it tidies your
   notes. Anything it can't decide alone shows up as a question when you next
   open Claude here. Say 'pause my caretaker' to stop it any time."

If the schedule tool isn't available in this session, stop and say the
caretaker needs cloud access on this Claude account; the workspace still
works, and session start covers the upkeep.

## Alternative runner (D67)

Only when the user's helper asks for it: `kit caretaker install --runner actions`
emits three GitHub Actions workflows on `claude-code-action` with a
subscription token stored as a repository secret. The helper does that setup;
it's not part of a normal onboarding.
