---
name: explain
description: >
  Explain a decision, tradeoff or technical choice to the user in their own
  terms, as a fixed-shape decision brief. Use before any non-trivial choice
  (a tool, a cost, a stack, a security setting, something the caretaker
  couldn't decide), when the user asks "why did you do that?", "what are my
  options?", "what does this mean?", or when writing a NEEDS-YOU item.
---

# Explain

A brief has one shape, always, so the user learns where to look:

1. **What I'm deciding.** One sentence, their words.
2. **Your options.** One line each. Two to four.
3. **What each costs you.** Time, money or risk, per option. Numbers where
   you have them.
4. **What I recommend, and why.** The pick and the one reason that matters
   most to this person.
5. **What you'd have to do.** Nothing, one click, a yes or no, or a decision
   by a date.

Get the template with:

```
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/kit.py" explain --template brief --title "<the decision>"
```

Or render a filled one from JSON (`title`, `deciding`, `options`, `costs`,
`recommendation`, `action`) with `kit explain --json <file>`.

## Writing it

- Read the "How the user learns" section of `AGENTS.md` first. Use the
  analogies it names (an accountant gets "source of record"; a bartender gets
  "the till has to balance"). If nothing fits, say it plainly without one.
- Short sentences. No code, no file paths, no git words. If a technical
  term is unavoidable, define it in the sentence and add it to the glossary:
  `kit glossary add "<term>" --meaning "<one plain sentence>"`.
- Run `unslop` on the whole brief.
- Be honest about uncertainty: "I don't know what this costs yet" beats a
  guess.

## Where it goes

- A decision inside an exploration or goal: into that packet's
  `DECISIONS.md`, under a dated heading.
- Something the caretaker couldn't decide: the brief is the body of the
  NEEDS-YOU item (`kit needs-you add --title "..." --brief-file <file>`).
- A quick answer in chat: the same five parts, in prose if that reads
  better. The shape is for the user's benefit, not a form to fill.

## When the user answers

Record it where the brief lives (the packet's `DECISIONS.md`, or
`kit needs-you resolve <id> --outcome "<what they chose>"`), then act on it.
If they pick an option you didn't recommend, do it their way and say nothing
more about it unless it's unsafe or costs money they didn't expect.
