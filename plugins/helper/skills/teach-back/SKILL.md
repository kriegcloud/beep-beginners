---
name: teach-back
description: >
  Explain what Claude just did, as a short lesson. Use when the user says
  "teach me what you just did", "explain that", "what did you just do", "how
  does that work", or "walk me through it".
---

# Teach back

The workspace `AGENTS.md` says what the user already knows and what they're
learning. Tie new ideas to that background.

1. Name what was done in one plain sentence.
2. Walk through it in three to six short steps. For each step, say what
   happened and why it matters. Explain each new term the first time it
   appears.
3. Give one comparison from the user's own background if it fits.
4. If a command or file was involved, show the one line that matters and say
   what each part does. Skip the rest.
5. End with one question that checks understanding, about this lesson only.
   Then wait for the answer.

Keep it under about 250 words unless the user asks for more. Run `unslop` on
it before sending.
