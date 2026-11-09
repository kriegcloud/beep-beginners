---
type: agent-config
title: Domain docs
description: "How the engineering skills read this workspace's glossary and decisions."
generated:
  by: process:kit
  at: "2026-11-08T00:00:00Z"
status: stable
---
# Domain docs

How the engineering skills read this workspace's domain documentation.

## Before exploring, read these

- `GLOSSARY.md` at the root. One glossary for the whole workspace; it is also
  the user's glossary, so every entry is one plain sentence.
- The goal's `DECISIONS.md` for decisions that touch the area you're working
  in. Goals are the decision records here; there is no `docs/adr/`.

If a file doesn't exist, proceed silently.

## Use the glossary's vocabulary

When your output names a concept, use the term as the glossary defines it.
A missing term is a signal: add it with `kit glossary add <term> --meaning "..."`
the first time it comes up, in words the user would use.

## Flag conflicts with earlier decisions

If your output contradicts a decision in a goal's `DECISIONS.md`, say so
plainly and explain why it's worth reopening, through an explain brief.
