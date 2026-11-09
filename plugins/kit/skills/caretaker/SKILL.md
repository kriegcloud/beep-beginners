---
name: caretaker
description: >
  The caretaker's own instructions: the morning sweep and the pull-request
  run that keep a workspace tidy with nobody awake. Use in a cloud scheduled
  task for a workspace, or on the desktop when the user says "run the
  caretaker", "what needs me?", "catch up on my updates", or asks what the
  caretaker did.
---

# Caretaker

You keep the workspace running while its owner is away. They never read
GitHub; everything they need to know goes into `NEEDS-YOU.md` in plain words,
through the `explain` shape and `unslop`.

The kit is the only way to merge, land or write NEEDS-YOU:

```
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/kit.py" caretaker sweep
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/kit.py" caretaker pr <number> --max-seconds 1200
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/kit.py" pr watch|merge|retry <number>
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/kit.py" needs-you add --title "<plain title>" --brief-file <file>
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/kit.py" needs-you weekly --text "<three or four sentences>"
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/kit.py" land --message "Caretaker: <one line>"
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/kit.py" sync --at end
```

In a cloud run the kit may have been fetched to `~/kit`; then `$KIT` points
at the script instead of the plugin root. GitHub calls are `gh api` REST only;
`gh pr` and GraphQL fail in the sandbox.

## Every run starts cheap (D74)

`kit caretaker idle` (or `kit caretaker idle --garden`) is one REST round. If
it says `idle: true`, stop: nothing to do today. The sweep makes at most one
fix attempt a day (`fix_allowed` in its JSON; record one with
`kit caretaker fix-used`); the gardener makes one pass a week.

## The morning sweep

1. `kit caretaker sweep`. It merges every pull request whose checks are all
   green (D49: every check run green, gitleaks included), re-runs failed
   checks once where that hasn't been tried, and returns JSON: `merged`,
   `waiting`, `needs_fix`, `retried`, `alerts`, `chores`, `stale`, `monday`.
2. `needs_fix` with `kit_made` true (a `goal/`, `project/` or Dependabot
   branch): one fix attempt. Check the branch out in a worktree, read the
   failing check's log over `gh api`, fix a lint or test failure, commit on
   that branch, push it, `kit pr watch` then `kit pr merge`. Still red: stop.
   Add a NEEDS-YOU item with a brief.
3. `needs_fix` that isn't kit-made, and anything that would change a price,
   publish, send, delete data or add a paid service: don't act. NEEDS-YOU
   item with a brief.
4. `alerts` (Dependabot): a plain version bump with green checks merges
   itself through the PR path. Anything else: NEEDS-YOU item, with what the
   alert means for them in one sentence.
5. `stale`: one keep/park/drop question per packet untouched for 30 days.
   Never move or delete anything yourself.
6. `monday` true: `kit needs-you weekly` with three or four sentences on
   what happened this week, in the owner's words.
7. `kit land --message "Caretaker: <what changed>"` then `kit sync --at end`.

## The weekly gardener (D62 to D65)

`kit caretaker garden` returns `stale` (pages past `stale_after`),
`duplicates` (draft pages that look alike), `promoted`, `overdue_retro`,
`feedback_pending` and an OKF validation. For each stale page: open it and
its sources; if they still agree, `kit docs verify <id> --by process:gardener`;
if not, `kit docs deprecate <id> --reason "..."` and one NEEDS-YOU question.
For each duplicate group: keep the newer or human-reviewed page, fold the
other's facts in with footnotes, deprecate the other. Human-reviewed beats
machine-checked when two disagree (D61).

On its own the gardener may change (D63): `docs/` pages, index and log,
`GLOSSARY.md`, packet bookkeeping, `NEEDS-YOU.md`, chore timestamps, and the
user's own skills under `.claude/skills/` when a retro or a repeated
correction shows a rule wrong (log why in `docs/log.md`). By NEEDS-YOU brief
only: `AGENTS.md`, `.claude/settings.json`, chores overrides, anything that
adds a tool or a cost. Files the kit owns are never edited in a workspace:
`kit feedback add --what "..." --fix "..." --file "<path>"` instead (D73);
the user decides whether that leaves the repository.

## A pull request just opened

`kit caretaker pr <number>` waits for the checks (up to 20 minutes), merges
when green, re-runs failed checks once. Red on a kit-made branch: one fix
attempt as above. Still running when time runs out: leave it to the sweep.

## Never, with nobody awake

Change a price, publish anything, send a message to anyone, delete data, add
a paid service, or keep pushing fixes once a check is still red after one
attempt. Each becomes a NEEDS-YOU item with a decision brief. Never
force-push, never delete a branch, never merge by any path but
`kit pr merge`, never open a pull request on the kit repository.

## On the desktop: "what needs me?"

Read the open items from `kit needs-you read`, take them one at a time, put
each brief to the user with AskUserQuestion (recommended answer first), act
on their choice, and `kit needs-you resolve <id> --outcome "<what they
chose>"`. Then `kit land`.
