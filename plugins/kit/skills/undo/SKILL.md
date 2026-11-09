---
name: undo
description: >
  Put the workspace's main copy back to an earlier safe point (D80). Use when
  the user says "undo", "go back to yesterday", "put it back how it was",
  "something broke since Tuesday", or asks what safe points exist. Never a
  force-push and nothing is deleted: the undo is a new step on top, and can
  itself be undone.
---

# Undo

The caretaker leaves a safe point (a tag called `safe/YYYY-MM-DD`) on the
GitHub backup every morning and keeps 30 days of them. `kit undo` restores the
main copy to one of them as a new commit, so nothing since is lost from
history, only moved out of the way.

Say first: "I can put everything back to how it was on any morning in the
last 30 days. Nothing gets deleted; it's one more step on top that we can
undo too."

1. `kit undo list` shows the safe points and which one main is at now. Read
   the dates out in plain words ("this morning", "yesterday", "last Tuesday").
2. Ask which one. Only a clear answer moves on.
3. If `kit land` would find unsaved changes, land them first (the user's
   current work is kept in history too).
4. `kit undo --to safe/<date>`. Read the JSON:
   - `via: main`: done. Say "The main copy is back to <day>. What changed
     since is still kept, so say 'undo the undo' if you change your mind."
   - `via: pull_request`: a lock on main asked for a pull request. Say "Put
     it back as finished work; the caretaker checks it and brings it in, in
     about an hour." Nothing more to do.
   - `reason: main already matches`: say so.
5. `kit sync --at end` so the local copy matches.

Never run git commands to do any of this by hand; the guard blocks them for
a reason (tags and history are the recovery net).
