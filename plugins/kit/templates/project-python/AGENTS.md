# {{name}}

{{summary}} {{goal_line}}

**Mode: {{mode}}.** The root `AGENTS.md` explains the two modes.

## Stack

Python 3.13 through uv. `uv run pytest` for tests, `uv run ruff check .` and
`uv run ruff format .` for style. No other tools without a reason written here.

## How work lands

- Save work with `kit land --message "<what changed>"`, never `git commit`. The
  kit puts this folder's changes on this project's branch and opens a pull
  request at the end of the session. The caretaker merges it when every check
  is green. The user never sees the pull request.
- Keep tests passing before landing. A red check is a NEEDS-YOU item by morning.
- Anything with a price, a payment, a message to someone, or deleting data:
  stop and ask the user first.

## Stages (Matt Pocock's engineering skills, agent-only)

Use them here and explain the result to the user through the `explain` skill,
never raw:

- Bigger than one session: `wayfinder`, tracked as markdown in the goal packet.
- Every change: `to-spec`, then `implement-spec`; the spec lives in the goal packet.
- While building: `tdd`. Before landing: `code-review`, findings fixed or
  waived in the packet.
- When the goal closes: `retro`, written into the packet.

## Data

Code lives here. Data files stay where `workspace.config` says; never copy
them into git.
