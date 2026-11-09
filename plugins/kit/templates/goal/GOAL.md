# Goal: {{title}}

These are the working instructions for this goal (D84). Start them by typing:

```
/goal follow the instructions in ./goals/{{slug}}/GOAL.md
```

`/goal` keeps Claude working turn after turn until a checker agrees these
instructions have been followed. The checker can't open files; it only reads
what Claude says. So every turn ends with one of the status lines at the
bottom, and stopping to wait for you counts as following the instructions.
`/goal` with nothing after it shows how it's going; `/goal clear` stops it.

## Start

1. Read this folder's `README.md` (what we're doing, "Done means",
   "Progress", "Trail"), `STEPS.md` (the working plan), and the exploration
   linked at the top of the README.
2. Read the mode in the workspace's `AGENTS.md`: operator (you do the steps)
   or mentor (you hand the user each step).
3. Say in the conversation, as a short list, every "Done means" line and
   which step is next. That list is what the checker holds you to.

Kit commands run as the `kit:make-goal` skill shows, with the kit's full
path. Load that skill once if you don't have the path. Never `git commit`;
`kit land` is the only way to save.

## Each step

1. Do the next unticked step in `STEPS.md` (operator mode), or give the user
   that step in plain words and stop (mentor mode).
2. Code lives under `projects/`, made with the `project` skill and worked by
   its `AGENTS.md`: `mattpocock-skills:to-spec`, then
   `mattpocock-skills:implement-spec`, `mattpocock-skills:tdd` while
   building, and `mattpocock-skills:code-review` before the branch lands
   (D70, D83). Specs and review notes go in this folder; code stays in the
   project.
3. Tick the step under "Progress", add a trail line with
   `kit goal set {{slug}} --trail "<what happened>"`, and save with
   `kit land --message "Goal: <one line>"`.

## Stop and hand back (this is following the instructions)

- A real choice (a tool, a cost, a tradeoff), or anything that changes a
  price, publishes, sends, deletes data or adds a paid service: write an
  explain brief (`explain` skill), ask, and stop.
- Mentor mode, after handing over a step: stop.
- The goal looks bigger, smaller or different than it did: say so plainly,
  offer to pause it, drop it, or go back to the exploration's plan stage,
  and stop. Never change "Done means" yourself.
- The same step fails twice, or a kit command keeps failing: stop and say
  what happened.
- About twenty turns in: `kit land` and stop, so the user can look.

## Finish

When every "Done means" line holds:

1. Run `mattpocock-skills:retro` and record it so it gets actioned (D65):
   `kit retro open --goal {{slug}} --summary "<three sentences through unslop>"`,
   then one `kit retro add --goal {{slug}} --text "..." --kind chore|step|decision|lesson --due <date>`
   per item.
2. `kit goal set {{slug}} --status done --trail "Done."` and
   `kit land --message "Goal done: {{title}}"`.

## End every turn with exactly one of these lines

- `Goal done:` then each "Done means" line with what shows it holds.
- `Waiting for you:` then the one question or decision.
- `Your turn:` then the step the user does (mentor mode).
- `Stuck:` then what failed and what was tried.
- `Pausing:` then where it stands.
- `Next:` then the step you start now, and keep going.
