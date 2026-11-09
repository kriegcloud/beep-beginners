---
name: project
description: >
  Make or work in a project folder under projects/: an app, a script, an
  automation, a data pipeline. Use when a goal needs code, when the user says
  "build me", "make a tool that", "automate", "bring my scripts in", or asks
  about an existing project. Picks the stack and explains the pick in one line.
---

# Project

Code lives under `projects/<name>/`, one folder per app or automation, each
with its own instructions, stack and tests. The user never chooses a stack,
never sees a branch or a pull request, and never runs a command. You pick,
you build, the kit lands it, the caretaker merges it.

## Making one

1. Pick the stack and say why in one line to the user:
   - **Python** (uv, ruff, pytest) for scripts, data work, automations,
     report feeds. The default.
   - **TypeScript** (bun, Biome, Vitest) only when the goal needs something
     that runs in a browser.
2. Run the kit from the workspace root:

   ```
   uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/kit.py" project new <name> --stack python|ts --goal <goal-slug> --summary "<one sentence>" [--mode mentor] [--from "<Documents folder>"]
   ```

   `<name>` is lowercase words joined by hyphens. `--goal` ties the folder to
   its goal, which names the branch its work lands on. `--mode mentor` for a
   learning project. `--from` copies code (never data) out of a Documents
   folder, with the user's OK first: "Copy your scripts from Documents into
   your workspace so they're backed up and versioned? Your data files stay
   where they are."
3. Read the new folder's `AGENTS.md`. It names the stack commands and the
   stages below.
4. Save with `kit land --message "Start the <name> project"`. The kit puts
   the folder on its branch; at the end of the session it pushes and opens
   the pull request. Tell the user: "I set up <name>. It's saved; the
   caretaker checks it overnight."

## Working in one

Follow the folder's `AGENTS.md`. The engineering stages are agent-only and
their output reaches the user only through `unslop` and an explain brief:

- Bigger than one session: `wayfinder` first. Its map lives in the goal
  packet under `wayfinder/`, as `docs/agents/issue-tracker.md` describes.
- Each change: `to-spec` (the spec goes in the goal packet's `specs/`), then
  `implement-spec`.
- `tdd` while building; the project's tests must pass before landing.
- `code-review` before the branch lands (D70). Fix what you can. For each
  finding left as it is, write one line with the reason into a waivers file,
  then record the review in the goal packet:
  `kit review record --goal <slug> --project <name> --findings N --fixed N --waivers <file>`
  (or `--no-waivers`). At session end the kit opens the pull request and
  posts the `kit/review` verdict on it; without that verdict the caretaker
  won't merge. If you push more commits after the review, review again.
- `retro` when the goal closes (see the `goal` skill).

Save often with `kit land`. Nothing else commits. Checks run on GitHub for
the folder; a red check becomes a NEEDS-YOU item by the next morning, and
the caretaker tries one fix itself first.

## Mentor mode

In a mentor-mode project the user writes the code. Give the next step, let
them do it, review it, then `kit land` with a message that names what they
did ("Sam added the import step"). Explain every new term the first time and
add it to the glossary.
