"""KIT-FEEDBACK.md (D73): what the kit got wrong, scrubbed, waiting for the
user's yes before it leaves the private repo as an issue on the kit."""

from __future__ import annotations

import re
from pathlib import Path

from . import github, needs_you
from .common import KitError, read_json, today, write_json

DOC = "KIT-FEEDBACK.md"
STATE = Path(".kit") / "feedback.json"
KIT_REPO = "kriegcloud/beep-beginners"

_SCRUB = [
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "<email>"),
    (re.compile(r"https?://\S+"), "<url>"),
    (re.compile(r"[A-Za-z]:\\[^\s`'\"]+"), "<path>"),
    (re.compile(r"/(?:home|Users)/[^\s/`'\"]+"), "<home>"),
    (re.compile(r"\b(?:ghp|gho|ghu|ghs|github_pat)_[A-Za-z0-9_]+"), "<token>"),
    (re.compile(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b"), "<phone>"),
]


def scrub(text: str) -> str:
    for rx, repl in _SCRUB:
        text = rx.sub(repl, text)
    return text


def load(root: Path) -> dict:
    return read_json(root / STATE, {"schema": "beep-beginners/feedback/v1", "notes": []})


def save(root: Path, state: dict) -> None:
    write_json(root / STATE, state)
    render(root, state)


def add(root: Path, what: str, fix: str, file: str = "") -> dict:
    state = load(root)
    note = {"id": f"note-{len(state['notes']) + 1}", "date": today(), "file": scrub(file), "what": scrub(what),
            "fix": scrub(fix), "sent": None}
    state["notes"].append(note)
    save(root, state)
    pending = [n for n in state["notes"] if not n["sent"]]
    if not any(i.get("kind") == "kit-feedback" for i in needs_you.load(root)["open"]):
        n = len(pending)
        brief = (f"**What I'm deciding.** The kit has {n} note{'s' if n != 1 else ''} for its maintainer about things it got wrong here. "
                 f"They hold no personal content (names, paths and addresses are scrubbed; you can read them in KIT-FEEDBACK.md).\n\n"
                 f"**Your options.**\n- Send them as one issue on the kit's public repository, under your GitHub name\n- Keep them private\n\n"
                 f"**What each costs you.**\n- Sending: nothing, and the fix may reach you through the next kit update\n- Keeping: the maintainer never hears\n\n"
                 f"**What I recommend, and why.** Send them; that is how the kit gets better for you.\n\n**What you'd have to do.** Say yes or no.")
        needs_you.add(root, "The kit has notes for its maintainer. Send them?", brief, source="gardener", kind="kit-feedback")
    return note


def send(root: Path) -> dict:
    """Open one issue on the kit with every unsent note. Only after the user's yes."""
    state = load(root)
    pending = [n for n in state["notes"] if not n["sent"]]
    if not pending:
        raise KitError("nothing to send")
    body = "Notes from a workspace's gardener (scrubbed by the kit, sent with the owner's yes).\n\n"
    for n in pending:
        body += f"### {n['date']}" + (f" in `{n['file']}`" if n["file"] else "") + f"\n\n**What went wrong.** {n['what']}\n\n**Fix it would make.** {n['fix']}\n\n"
    issue = github.api(f"repos/{KIT_REPO}/issues", "POST",
                       raw={"title": f"Workspace feedback, {today()} ({len(pending)} note{'s' if len(pending) != 1 else ''})", "body": body})
    for n in pending:
        n["sent"] = {"date": today(), "issue": issue.get("html_url")}
    save(root, state)
    return {"sent": len(pending), "issue": issue.get("html_url")}


def render(root: Path, state: dict | None = None) -> str:
    state = state or load(root)
    lines = ["# Notes for the kit's maintainer", "",
             "The gardener writes here when a file the kit owns got something wrong in this workspace.",
             "Names, paths, addresses and tokens are scrubbed. Nothing leaves this private repository",
             "until you say yes to sending it, which opens one issue on the kit under your GitHub name.", ""]
    for n in state["notes"]:
        status = f"sent {n['sent']['date']}" if n["sent"] else "not sent"
        lines += [f"## {n['date']} ({status})", ""]
        if n["file"]:
            lines.append(f"File: `{n['file']}`")
            lines.append("")
        lines += [f"**What went wrong.** {n['what']}", "", f"**Fix it would make.** {n['fix']}", ""]
    if not state["notes"]:
        lines += ["Nothing yet.", ""]
    text = "\n".join(lines)
    (root / DOC).write_text(text, encoding="utf-8")
    return text
