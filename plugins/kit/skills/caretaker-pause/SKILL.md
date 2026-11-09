---
name: caretaker-pause
description: >
  Pause or resume the caretaker's cloud tasks from a session (D74). Use when
  the user says "pause my caretaker", "stop the caretaker", "turn the
  caretaker back on", "is the caretaker running?", or asks how much Claude it
  uses.
---

# Pause or resume the caretaker

The caretaker is three cloud tasks on the user's Claude account. Pausing
flips their on/off switch; nothing is deleted, and resuming flips it back.

1. Run `kit caretaker pause` to get the routine ids (`sweep`, `pr_opened`,
   `garden`). If there are none, say the caretaker isn't set up and offer
   the `caretaker-setup` skill.
2. Invoke the `schedule` skill and, for each id, call the schedule tool's
   update action with `enabled: false` (pause) or `enabled: true` (resume).
3. Say in one sentence what changed: "Your caretaker is paused; nothing runs
   while you're away until you say 'turn it back on'." or "Your caretaker is
   back on; the next check is tomorrow morning."

While paused, session start still does the upkeep it can: kit updates,
finished work that passed its checks, the index, the backup check.

If the user asks how much Claude the caretaker uses: each run is a short
Claude session on their account, one a day plus one per finished piece of
work plus one a week. If a run is rejected at their usage limit, the kit
leaves one line in NEEDS-YOU.md; nothing retries until the limit resets.
