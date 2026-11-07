---
name: helper-access
description: >
  Turn the helper's remote access to this PC on or off, or say whether it's on.
  Use when the user says "stop <helper>'s access", "turn off remote access",
  "let <helper> back in", "turn <helper>'s access back on", or "can <helper>
  get into my computer right now?". The helper's name is in the workspace
  AGENTS.md.
---

# Helper access

The helper reaches this PC through Tailscale and Windows OpenSSH Server, only
with their own key, and only over Tailscale. Onboarding set that up. This
skill flips the switch.

Script: `uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/remote_access.py" <status|on|off>`

- **Status.** Run `status` and answer in one sentence: "<Helper> can connect
  right now" or "<Helper>'s access is off."
- **Off.** Say in one sentence: "Windows will ask once for permission, then
  <helper> won't be able to connect until you turn it back on." Run `off`.
  Confirm with `status` and tell the user it's off.
- **On.** Same pattern with `on`. Mention that the helper still connects only
  when the user asks them to.

If the Windows permission prompt is declined, say that nothing changed. If
the script fails, use the `help-request` skill, but only after turning access
on would actually help.
