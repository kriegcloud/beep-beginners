---
name: kit-grill
description: >
  Ask the user the hard questions about an idea, plan or decision in their
  own terms, one decision per question, with a recommended answer first. Use
  in the explore skill's decide stage, for wayfinder grilling tickets, and
  whenever a plan has open decisions the user should make. Wraps Matt Pocock's
  grilling skill for someone who doesn't code.
---

# Grill, for the user

This wraps the `grilling` skill (from Matt Pocock's set). Grilling's method
stands: map the decisions as a tree, ask the whole frontier of answerable
questions in one round, recommend an answer for each, let the user's answers
reshape the tree, repeat until nothing is silently assumed. What changes is
the audience.

## Rules

- **Read "How the user learns" in `AGENTS.md` first** and write every
  question to it. Use their analogies. Define any term you can't avoid, and
  add it to the glossary with `kit glossary add`.
- **One decision per question.** Never two joined by "and". If a question
  needs a fact, find the fact yourself first (web, workspace, sub-agent);
  the user only ever decides.
- **Recommended answer first**, marked so "yes" accepts it, with the one
  reason that matters to them in a line. Give the real tradeoff in a line
  when there is one: time, money, risk.
- **Use AskUserQuestion** for each round, up to four questions a round, only
  questions that don't depend on another open one. The recommended option
  goes first with "(Recommended)".
- **Plain words.** No code, no file paths, no git or GitHub words. Short
  sentences. Run `unslop` on the question text.
- **Log every answer** where the decision lives: the packet's `DECISIONS.md`
  (question, answer, why), or the wayfinder ticket's `## Answer`. Save with
  `kit land`.
- **Stop when the frontier is empty**, then say in two sentences what was
  settled and what happens next. Don't act on the answers until the user has
  seen that summary.

## Example round

Two questions, both answerable now:

- Q1. Should the first version of the ledger run on your laptop only, or be
  something you can open on your phone too? Recommended: laptop only. It's
  the smaller build, and nothing you've said needs the phone yet. Cost of
  the other: a few extra weeks before anything works.
- Q2. Keep bundles as single sales for now, or split them per card?
  Recommended: single sales. It matches how your workbook records them, so
  the numbers tie out; splitting can come later when the cost basis is in.
