---
name: explore
description: >
  Think an idea through with the user and write it up as a plain-English packet
  in explorations/. Use when the user says "I want to explore X", "help me figure
  out whether to X", "I've been thinking about X", "should I X", or asks about
  an existing exploration ("where are we on the security company idea?"). Also
  use for "what am I exploring?" and for parking or dropping an idea.
---

# Explore

An exploration takes a fuzzy idea to one of three endings: it becomes one or
more goals, it gets parked for later, or it gets dropped. Dropping an idea is
a good result. It means the thinking got done.

The user reads every packet file except `.packet.json`. Write them for someone
smart who doesn't code: plain words, short sentences, no code, no file paths
in prose, no jargon unless it's explained the first time (and then added to
`GLOSSARY.md` with `kit glossary add`). Run the `unslop` skill on every file
before saving it. Read the "How the user learns" section of `AGENTS.md` first
and write to it.

## Bookkeeping

Run the kit for every state change and every save. Never hand-edit
`.packet.json` or the `INDEX.md` files, and never run `git commit` yourself.

```
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/kit.py" explore new "<title>" --notes "<their words>"
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/kit.py" explore set <slug> --stage <stage> --next "<question>" --trail "<what happened>"
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/kit.py" explore set <slug> --status parked|dropped --trail "<why, in one line>"
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/kit.py" goal graduate <slug> "<goal title>" --mission "<one sentence>"
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/kit.py" explore list
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/kit.py" land --message "<one line the user would understand>"
```

Run them from the workspace root (or pass `--root <workspace>` when the
session is open elsewhere, as onboarding's hand-off does). Save after each
stage with `kit land`, with a message such as "Explore: research on starting a
security company".

## Starting

1. If the idea matches an existing packet (`kit explore list`), resume that one.
2. Otherwise run `explore new` with a short title in the user's words and their
   message as `--notes`.
3. Fill in "What this is about" in the README with one paragraph.
4. Tell the user in one or two sentences what happens next.

## Stages

**notes.** Put whatever the user says into `NOTES.md` under a dated heading,
word for word. Don't question them yet. Move on when they're done talking or
say "go ahead".

**research.** Look things up on the web and in the workspace. Write
`RESEARCH.md` in dated sections, and link every fact to its source. Cover
costs, rules or licenses, how other people do it, and what the user already
has that helps. Say plainly when something couldn't be confirmed.

**decide.** Use the `kit-grill` skill: it asks the open questions in the
user's terms, one decision per question, with your recommended answer first.
Use what's known about the user (their background, money, time, the people
involved) to make options concrete. Log each answer in `DECISIONS.md` as
question, answer and why. Keep going round by round until nothing important
is open. A new gap in the research means a short trip back to research, noted
in the trail. A decision with real tradeoffs gets an explain brief
(`explain` skill) in `DECISIONS.md`, not just a line.

**plan.** Write `PLAN.md`: the problem, how much time and money it's worth,
the idea at a rough level, risks, what's out of scope, and the goals it turns
into, with the smallest useful one first. Say in one line whether a goal
needs code and which stack the `project` skill would pick (Python unless it
needs a browser UI). Ask the user whether it matches what they had in mind.
Revise until it does.

**graduate.** For each goal the user wants to start now, run `goal graduate`,
then fill in the goal's README ("Done means" and "Progress") and `STEPS.md`.
When every goal they wanted exists, set the exploration's status to
`graduated`. Goals they want "later" stay listed in `PLAN.md`.

## Ending a session

Before stopping, always:

1. run `explore set` with the current stage, the next open question and a trail line;
2. `kit land`;
3. tell the user in one sentence where it stands and what the next question is.

If momentum dies, offer to park it (with the reason) or drop it (with a
one-line epitaph). Never leave a packet looking active when nobody is working
on it. The caretaker asks about packets untouched for a month; answer its
question rather than letting it ask twice.

## Example opening

User: "I want to figure out whether to start a security company."

You: run `explore new`, save their words, then say something like: "I started
a notes page for this. Tell me whatever's on your mind about it: who it's
for, what's bugging you, what you've already tried. When you're done I'll look
into the costs and rules and come back with questions."
