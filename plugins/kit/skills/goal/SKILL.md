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
are plain English and go through `unslop` before saving. The folder also
holds whatever the engineering skills produce for it: specs, tickets, a
wayfinder map, a retro. The user can open all of it in OpenKnowledge.

## Working a goal

1. Read the goal's README, `STEPS.md`, and the exploration it came from
   (linked at the top of the README).
2. Check which mode the folder's `AGENTS.md` sets. In operator mode, do the
   next step. In mentor mode, give the user the next step and let them do it.
3. If the goal needs code, the `project` skill makes the folder under
   `projects/`. Work on code happens there, following its `AGENTS.md`: spec,
   implement, tests, review. The goal packet holds the spec and the review
   notes; the project folder holds the code.
4. After each step, tick it in "Progress", add a trail line with
   `kit goal set <slug> --trail "<what happened>"`, and save with
   `kit land --message "Goal: <one line>"`.
5. When everything in "Done means" holds, run `retro` (agent-only), then
   record it so it gets actioned (D65):
   `kit retro open --goal <slug> --summary "<three sentences through unslop>"`,
   and one `kit retro add --goal <slug> --text "..." --kind chore|step|decision|lesson --due <date>`
   per item. A recurring fix is a `chore`, a one-off a `step` (it lands in
   `STEPS.md`), something only the user can decide a `decision` (a NEEDS-YOU
   brief), a lesson a `lesson` (a page under `docs/lessons/` with the retro as
   its source). Every item gets a due date; the gardener nags once about
   overdue ones. The retro opens with the previous retro's scorecard.
   Then `kit goal set <slug> --status done --trail "Done."` and tell the user.

The kit lives at `${CLAUDE_PLUGIN_ROOT}/scripts/kit.py`. Run it with
`uv run --script` from the workspace root. Never `git commit`.

## Explaining along the way

Any step with a real choice in it (a tool, a cost, a tradeoff) gets an
explain brief first (`explain` skill), in the user's terms. Terms go into
`GLOSSARY.md` the first time.

## If the goal turns out wrong

If a goal is bigger, smaller or different than it looked, say so plainly.
Offer to pause it, drop it, or go back to the exploration's plan stage. Don't
quietly change what "done" means. A goal bigger than one session gets a
`wayfinder` map in the packet before any code.
