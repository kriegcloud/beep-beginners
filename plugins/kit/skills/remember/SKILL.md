---
name: remember
description: >
  Write what a session learned into docs/, the workspace's memory of record
  (D64, D71). Use near the end of any session where the user stated a
  preference, corrected you, told you a fact about their business or how they
  work, or a lesson emerged; also when the user says "remember that", "note
  that down", or "don't forget". Never for anything on the never-list below.
---

# Remember

`docs/` is the memory of record. Claude Code's own auto-memory is a cache
that can be rebuilt from it, and the cloud never sees that cache. Anything
durable goes in as a page with a type, a source and a `draft` status; the
gardener promotes it to `stable` after a week unless someone objects.

## What may be written (D71)

Only these types: `preference` (how they like things done), `business-fact`
(a fee, a supplier, a rule of their business), `workflow` (how a recurring
task goes), `correction` (something you got wrong and the right version),
`lesson` (what a retro or a mistake taught).

## Never written down

Health. Relationships. Finances beyond the business (personal income, debts,
accounts). A third person by name. Credentials, tokens, account numbers.
Anything the user said not to write down. When in doubt, don't; ask once if
it matters.

## How

```
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/kit.py" docs new --export --type <type> --title "<plain title>" --body "<one short paragraph, their words where possible>" --description "<one sentence>" --source "<where it came from: the session date, a packet path, a URL>" --by "<producer>/<version>"
```

`--by` is the actor convention: `claude-code/<model>` for you, `human:<name>`
only when the user themselves wrote or confirmed the text. The kit sets
`status: draft`, `generated`, and a `stale_after` from the type's default
(money and account facts 30 days, preferences 180, workflows 90).

Then say one line to the user, and only one: "I noted that you prefer X;
say 'drop it' if not." If they say drop it:
`kit docs deprecate <id> --reason "the user asked"`.

When the user confirms a fact in conversation ("yes, that's right"), record
it: `kit docs verify <id> --by human:<name>`. Human-reviewed pages outrank
machine-checked ones when two disagree.

Save with `kit land --message "Remember: <one line>"`.
