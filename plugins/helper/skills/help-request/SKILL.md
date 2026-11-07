---
name: help-request
description: >
  Use when something is broken and you can't fix it after a real try: a tool
  won't install or run, a sign-in keeps failing, git or GitHub errors you can't
  clear, a hook that blocks normal work. Also use when the user says "I need
  help", "ask my helper", "get <helper's name>" or "this is broken".
---

# Help request

The user's helper is named in the workspace `AGENTS.md`. The helper connects
only when asked, so the request has to stand on its own.

1. Write `HELP-REQUEST.md` at the workspace root, replacing any old one:
   - **What broke.** One or two sentences in plain words.
   - **When.** Date and time, and what the user was trying to do.
   - **What I tried.** Each attempt and what happened.
   - **Exact error.** Copy it word for word in a code block. Remove anything
     that looks like a password, token, key, or account number first.
   - **Machine.** OS version, and the output of `claude --version`,
     `git --version`, `uv --version`, `gh auth status` (account name only).
   - **Remote access.** Say whether it's on. Find out by running
     `uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/remote_access.py" status`.
     Put only the true/false answers in the request.
2. Never include secrets, file contents from `.env` or key files, or
   1Password item values. Paths and names are fine.
3. Commit it ("Help request: <short title>") and push, so the helper can read
   it on GitHub.
4. Tell the user, in about two sentences: what broke, and to text their
   helper "I left a help request in my workspace." If remote access is off,
   add that the helper can't connect until the user says "turn <helper's
   name>'s access back on".

When the problem is fixed, delete `HELP-REQUEST.md` and commit
("Help request resolved: <short title>").
