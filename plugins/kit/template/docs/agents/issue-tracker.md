---
type: agent-config
title: Issue tracker: local markdown inside goal packets
description: "Where specs, tickets and wayfinder maps live."
generated:
  by: process:kit
  at: "2026-11-08T00:00:00Z"
status: stable
---
# Issue tracker: local markdown inside goal packets

Specs, tickets and wayfinder maps for this workspace live as markdown files
inside the goal they belong to, so the user can read them in OpenKnowledge.
There is no `.scratch/`.

## Conventions

- One goal per directory: `goals/<goal-slug>/`.
- The spec for a change is `goals/<goal-slug>/specs/<NN>-<slug>.md`, numbered from `01`.
- Implementation tickets are one file each at `goals/<goal-slug>/issues/<NN>-<slug>.md`, numbered from `01`, never one combined file.
- Triage state is a `Status:` line near the top of each ticket (role strings in `triage-labels.md`).
- Comments and history append under a `## Comments` heading at the bottom.
- Everything a person might read goes through `unslop` first.

## When a skill says "publish to the issue tracker"

Create the file under the goal's folder (make `specs/` or `issues/` if needed), then save with `kit land`.

## When a skill says "fetch the relevant ticket"

Read the file at the path given. The user normally names the goal, not the file.

## Wayfinding operations

Used by `wayfinder`. The **map** is a file with one **child** file per ticket.

- **Map**: `goals/<goal-slug>/wayfinder/map.md` (Destination / Notes / Decisions so far / Not yet specified / Out of scope).
- **Child ticket**: `goals/<goal-slug>/wayfinder/issues/NN-<slug>.md`, numbered from `01`, the question in the body. A `Type:` line records the ticket type (`research`/`prototype`/`grilling`/`task`); a `Status:` line records `claimed`/`resolved`.
- **Blocking**: a `Blocked by: NN, NN` line near the top. A ticket is unblocked when every file it lists is `resolved`.
- **Frontier**: scan `goals/<goal-slug>/wayfinder/issues/` for files that are open, unblocked and unclaimed; lowest number wins.
- **Claim**: set `Status: claimed` and save before any work.
- **Resolve**: append the answer under `## Answer`, set `Status: resolved`, then add a one-line gist with a link to the map's Decisions so far.
- Grilling tickets use the `kit-grill` skill, so the questions reach the user in their own terms.
- Research branches are not used here: research findings are written into the goal's `RESEARCH.md` and saved with `kit land`.
