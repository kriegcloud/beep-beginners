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
in prose, no jargon unless it's explained the first time. Run the `unslop`
skill on every file before saving it.

## Bookkeeping

Run the packet script for every state change. Never hand-edit `.packet.json`
or the `INDEX.md` files.

```
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/packet.py" new "<title>" --notes "<their words>"
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/packet.py" set <slug> --stage <stage> --next "<question>" --trail "<what happened>"
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/packet.py" set <slug> --status parked|dropped --trail "<why, in one line>"
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/packet.py" graduate <slug> "<goal title>" --mission "<one sentence>"
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/packet.py" list
```

Run them from the workspace root. Commit after each stage with a one-line
message the user would understand, such as "Explore: research on starting a
security company".

## Starting

1. If the idea matches an existing packet (`packet.py list`), resume that one.
2. Otherwise run `new` with a short title in the user's words and their
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

**decide.** Ask the open questions with AskUserQuestion. Ask up to four at a
time, only questions that don't depend on another open one. Put your
recommended answer first, marked "(Recommended)", with the reason in its
description. Use what's known about the user (their background, money,
time, the people involved) to make options concrete. Log each answer in
`DECISIONS.md` as question, answer and why. Keep going round by round until
nothing important is open. A new gap in the research means a short trip back
to research, noted in the trail.

**plan.** Write `PLAN.md`: the problem, how much time and money it's worth,
the idea at a rough level, risks, what's out of scope, and the goals it turns
into, with the smallest useful one first. Ask the user whether it matches
what they had in mind. Revise until it does.

**graduate.** For each goal the user wants to start now, run `graduate`, then
fill in the goal's README ("Done means" and "Progress") and `STEPS.md`. When
every goal they wanted exists, set the exploration's status to `graduated`.
Goals they want "later" stay listed in `PLAN.md`.

## Ending a session

Before stopping, always:

1. run `set` with the current stage, the next open question and a trail line;
2. commit;
3. tell the user in one sentence where it stands and what the next question is.

If momentum dies, offer to park it (with the reason) or drop it (with a
one-line epitaph). Never leave a packet looking active when nobody is working
on it.

## Example opening

User: "I want to figure out whether to start a security company."

You: run `new`, save their words, then say something like: "I started a
notes page for this. Tell me whatever's on your mind about it: who it's for,
what's bugging you, what you've already tried. When you're done I'll look
into the costs and rules and come back with questions."
