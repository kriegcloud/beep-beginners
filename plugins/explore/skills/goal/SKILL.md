---
name: goal
description: >
  Work on a goal in goals/: something an exploration graduated into. Use when
  the user says "work on <goal>", "what's next on <goal>", "how far along is
  <goal>", "what are my goals", or marks a goal done or paused.
---

# Goal

A goal folder has a `README.md` the user reads (what we're doing, what done
means, progress, trail) and a `STEPS.md` that is Claude's working plan. Both
are plain English and go through `unslop` before saving.

## Working a goal

1. Read the goal's README, `STEPS.md`, and the exploration it came from
   (linked at the top of the README).
2. Check which mode the folder's `AGENTS.md` sets. In operator mode, do the
   next step. In mentor mode, give the user the next step and let them do it.
3. After each step, tick it in "Progress", add a trail line with
   `packet.py goal-set <slug> --trail "<what happened>"`, and commit with a
   one-line message such as "Goal: priced the first month of staffing".
4. When everything in "Done means" holds, run
   `packet.py goal-set <slug> --status done --trail "Done."` and tell the user.

The script lives at `${CLAUDE_PLUGIN_ROOT}/scripts/packet.py`. Run it with
`uv run --script` from the workspace root.

## If the goal turns out wrong

If a goal is bigger, smaller or different than it looked, say so plainly.
Offer to pause it, drop it, or go back to the exploration's plan stage. Don't
quietly change what "done" means.
