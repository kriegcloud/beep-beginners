---
name: make-goal
description: >
  Make a goal packet in goals/ from an exploration, and hand the user the
  `/goal` line that works it (D84). Use at an exploration's graduate stage,
  when the user says "make a goal for <idea>", "start <goal>", "work on
  <goal>", "what's next on <goal>", "how far along is <goal>", "what are my
  goals", or pauses, drops or finishes a goal.
---

# Make a goal

A goal packet is the plan; Claude Code's built-in `/goal` is how it runs.
This skill makes and maintains the packet. It never works the steps itself.

A goal folder holds `README.md` (what we're doing, what done means,
progress, trail; the user reads it), `STEPS.md` (Claude's working plan),
`GOAL.md` (the instructions `/goal` follows) and whatever the engineering
skills produce for it: specs, tickets, a wayfinder map, reviews, a retro.
All plain English through `unslop`; the user can open all of it in
OpenKnowledge.

## Kit commands

```
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/kit.py" goal graduate <exploration-slug> "<goal title>" --mission "<one sentence>"
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/kit.py" goal set <slug> --status active|paused|done|dropped --trail "<one line>"
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/kit.py" goal set <slug> --trail "<what happened>"
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/kit.py" explore list
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/kit.py" land --message "<one line>"
```

Run them from the workspace root. When `GOAL.md` says "kit", it means this
full path. Never `git commit`, never hand-edit `.packet.json` or `INDEX.md`.

## Making a goal

A goal comes from an exploration. If the user has an idea with no
exploration yet, start one with the `explore` skill; a small idea can move
through it in one sitting.

1. `kit goal graduate <exploration-slug> "<title>" --mission "<one sentence>"`.
   It copies the packet, fills the title, slug and dates, and links the
   exploration.
2. Fill "Done means" in `README.md` with three to six lines a stranger could
   check from what Claude says: "the price list has a column for shipping",
   not "pricing is better". `/goal`'s checker holds the run to exactly these
   lines, so a vague one never finishes.
3. Fill "Progress" with the steps as unticked boxes and write `STEPS.md`:
   each step says what it does and how we'll know it worked. A goal bigger
   than one session gets a `mattpocock-skills:wayfinder` map in the packet
   first.
4. Leave `GOAL.md` as the kit wrote it unless this goal needs an extra stop
   rule (say, "never contact a customer"); add it under "Stop and hand back".
5. `kit land --message "Goal: made <title>"`.
6. Tell the user, in one short paragraph through `unslop`, what the goal is,
   what done means, and how to start it. Give the line on its own so they
   can copy it:

   ```
   /goal follow the instructions in ./goals/<slug>/GOAL.md
   ```

   Say that `/goal` on its own shows progress and `/goal clear` stops it. If
   they are not in auto mode, say they'll be asked before some steps run.

## "Work on <goal>" and "what's next"

Don't start the steps here. Read the README's "Progress" and the last trail
lines, say in two sentences where it stands, and give the `/goal` line. If a
`/goal` run is already going in this session, say so instead.

## Status, pause, drop, done

- "What are my goals": `kit explore list` and the goals' READMEs; one line
  each with its status and next step.
- "How far along": the ticked and unticked "Progress" lines, in plain words.
- Pause or drop: `kit goal set <slug> --status paused|dropped --trail "<why>"`,
  then `kit land`. Dropping is fine; say so.
- Finishing happens inside the `/goal` run (`GOAL.md` "Finish"). If the user
  says a goal is done outside a run, check every "Done means" line first; if
  any doesn't hold, say which and don't mark it.

## If the goal turns out wrong

If a goal is bigger, smaller or different than it looked, say so plainly.
Offer to pause it, drop it, or go back to the exploration's plan stage.
Don't quietly change what "done" means; a change to "Done means" is the
user's call and gets a trail line.

## Explaining along the way

Any real choice (a tool, a cost, a tradeoff) gets an explain brief first
(`explain` skill), in the user's terms. Terms go into `GLOSSARY.md` the first
time.
