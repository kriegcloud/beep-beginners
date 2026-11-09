---
name: caretaker-setup
description: >
  The second sitting (D68): set up the caretaker that tidies the workspace
  while the user is away. Use when the caretaker-setup chore asks "Ten minutes
  to set up your caretaker?" and the user says yes, or when the user says "set
  up my caretaker", "turn on the caretaker", or asks why nothing happens while
  they're away. Needs a Max plan; on Pro, explain what upgrading unlocks.
---

# Caretaker setup

Three cloud tasks run on the user's own Claude account: a morning sweep, a
run whenever finished work is waiting to be checked, and a weekly gardener on
Sunday night. They use the user's subscription (D66), so this is their call.

Say first, in two sentences: "The caretaker runs on your Claude account while
you're away: it merges finished work that passed its checks, reads security
notices, and tidies your notes once a week. It uses a little of your Claude
each day, and you can pause it any time by saying 'pause my caretaker'."

## Plan check (D66)

The plan is in `.kit/profile.json` or the onboarding answers (`claude_plan`).
If it isn't Max 5x or higher, stop here and say: "The caretaker needs a Max
plan, because cloud tasks draw from the same usage pool as your own sessions
and stop at the limit. On Pro, the kit does the same upkeep whenever you open
Claude here: finished work that passed its checks goes into the main copy at
the start of your session. If you upgrade later, say 'set up my caretaker'."
Record it: `kit caretaker record --plan pro`.

## Steps (each announced in one sentence before it happens)

1. **GitHub App.** "Claude's cloud helper needs permission to see your
   workspace on GitHub. GitHub will show an Install button; click it, choose
   your account, and pick only the workspace repository." Open
   https://github.com/apps/claude in Chrome. Check with
   `gh api repos/<owner>/<repo>/installation`: 200 means installed.
   Save `state.py answer github_app true`.
2. **Cloud onboarding.** Open https://claude.ai/code in Chrome, signed in as
   the same Claude account as this app. If it shows a GitHub connect step or
   offers a first environment ("Default"), tell the user to accept it. If it
   opens straight to the session list, it's done.
3. **Bodies.** Run `workspace.py cloud-ready` for the workspace URL and the
   UTC cron for 7:07 local, then
   `kit caretaker install --workspace <url> --environment <env id> --cron-utc "<cron>" --garden-cron-utc "<Sunday 21:07 local in UTC>" --route <route> --ref <ref>`.
   The environment id is the account's Default cloud environment (the
   `schedule` skill lists them). `--route` and `--ref` come from the kit's
   `docs/DECISIONS.md` D45 amendment; the default is `fetch` on `stable`.
4. **Create.** Invoke the `schedule` skill. Create `sweep`, then `pr_opened`,
   then `garden`, each with the schedule tool's create action and the body
   as given (Opus 5.5, medium, no connectors). Then `create_webhook_trigger`
   with the webhook spec and `pr_opened`'s id for `pull_request.opened` on
   the workspace repository.
5. **Record.** `kit caretaker record --sweep <id> --pr <id> --garden <id> --plan max5`,
   then `kit land --message "Set up the caretaker"` and `kit sync --at end`.
6. **Say** in two sentences what will happen: "Every morning around seven the
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
