"""Profiles (D55): a Claude memory export plus a short interview becomes the
AGENTS.md slots and the user's personal skills in .claude/skills/.

`draft` turns the pasted memories into structure the agent reasons over:
dated entries by section, and the interview questions with what the memories
already answer. `write` takes the agent's answers (a JSON file) and writes
the workspace. The raw memories are never written to the workspace.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .common import KitError, slugify

QUESTIONS = [
    {"key": "work", "ask": "What do you do, and what did you do before?",
     "hints": ("career", "identity", "work", "job", "degree")},
    {"key": "build", "ask": "What do you want to build or figure out first?",
     "hints": ("project", "want", "goal", "learning", "idea", "business")},
    {"key": "help_style", "ask": "How do you like to be helped: step by step, or just get it done?",
     "hints": ("mentor", "teach", "explain", "quiz", "ask", "clarif")},
    {"key": "learn", "ask": "When something new comes up, what helps it land? Examples from your own field?",
     "hints": ("learn", "analog", "land", "background", "concept")},
    {"key": "subscriptions", "ask": "Which AI subscriptions do you pay for? Claude, ChatGPT, Grok, Gemini.",
     "hints": ("chatgpt", "codex", "grok", "gemini", "subscription")},
    {"key": "helper", "ask": "Who helps you when something breaks on this computer?",
     "hints": ("helper", "benjamin", "friend", "brother", "sister", "cousin")},
]

_ENTRY = re.compile(r"^\[(?P<date>[^\]]*)\]\s*-\s*(?P<text>.+)$")
_SECTION = re.compile(r"^##\s*\d*\.?\s*(?P<name>.+?)\s*$")
_SLOT = re.compile(r"<!-- slot:(?P<name>[a-z-]+) -->\n.*?<!-- /slot:(?P=name) -->", re.S)


def parse_memories(text: str) -> dict:
    """Claude's memory export: `## N. Section` headings, `[date] - text` lines.
    Anything else is kept as free text under 'notes'."""
    sections: dict[str, list[dict]] = {}
    current = "notes"
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = _SECTION.match(line)
        if m:
            current = m.group("name").strip().lower()
            sections.setdefault(current, [])
            continue
        m = _ENTRY.match(line)
        if m:
            sections.setdefault(current, []).append({"date": m.group("date").strip(), "text": m.group("text").strip()})
        else:
            sections.setdefault(current, []).append({"date": "", "text": line})
    return sections


def draft(memories_text: str) -> dict:
    sections = parse_memories(memories_text)
    everything = [e["text"] for entries in sections.values() for e in entries]
    lower = " ".join(everything).lower()
    questions = []
    for q in QUESTIONS:
        evidence = [t for t in everything if any(h in t.lower() for h in q["hints"])]
        questions.append({"key": q["key"], "ask": q["ask"], "answered_by_memories": bool(evidence),
                          "evidence": evidence[:6]})
    instructions = [e["text"] for e in sections.get("instructions", [])]
    projects = [e["text"] for e in sections.get("projects", [])]
    skill_candidates = []
    for text in instructions + projects:
        head = text.split(":", 1)[0].strip()
        if 3 <= len(head) <= 60 and "," in head or " - " in text[:80] or head.lower().startswith(("mercari", "morning", "mentor", "job")):
            skill_candidates.append(head.rstrip(",").strip())
    subscriptions = [s for s in ("claude", "chatgpt", "grok", "gemini") if s in lower]
    return {
        "sections": {k: len(v) for k, v in sections.items()},
        "entries": sections,
        "questions": questions,
        "still_to_ask": [q["ask"] for q in questions if not q["answered_by_memories"]],
        "skill_candidates": sorted(set(skill_candidates))[:8],
        "subscriptions_seen": subscriptions or ["claude"],
        "answers_template": {
            "name": "", "about": "", "how_i_learn": [], "folders": [],
            "helper": {"name": "", "keys_url": ""}, "subscriptions": subscriptions or ["claude"],
            "skills": [{"name": "", "description": "", "body": ""}],
            "first_exploration": "",
        },
    }


def set_slot(text: str, slot: str, body: str) -> str:
    pattern = re.compile(rf"<!-- slot:{slot} -->\n.*?<!-- /slot:{slot} -->", re.S)
    if not pattern.search(text):
        raise KitError(f"AGENTS.md has no slot named {slot}")
    # Keep the markers so the profile can be rewritten later without losing its place.
    return pattern.sub(lambda _: f"<!-- slot:{slot} -->\n{body.rstrip(chr(10))}\n<!-- /slot:{slot} -->", text, count=1)


def _validate(answers: dict) -> None:
    for key in ("name", "about"):
        if not answers.get(key):
            raise KitError(f"answers need a {key}")
    for skill in answers.get("skills", []):
        if not skill.get("name") or not skill.get("description") or not skill.get("body"):
            raise KitError("every skill needs a name, a description and a body")
        if slugify(skill["name"]) != skill["name"]:
            raise KitError(f"skill name {skill['name']!r} must be lowercase words joined by hyphens")


def write(root: Path, answers: dict) -> dict:
    _validate(answers)
    agents_path = root / "AGENTS.md"
    text = agents_path.read_text(encoding="utf-8")
    name = answers["name"]
    text = set_slot(text, "about", f"The user is {name}.\n\n{answers['about'].strip()}")
    learn = answers.get("how_i_learn") or []
    learn_text = "\n".join(f"- {line.strip()}" for line in learn) if learn else \
        "- Plain words first. Explain a new term the first time it comes up."
    text = set_slot(text, "how-i-learn", learn_text)
    folders = answers.get("folders") or []
    folder_lines = []
    for f in folders:
        folder_lines.append(f"- `{f['name']}/`: {f['summary'].strip()}")
    text = set_slot(text, "folders", "\n".join(folder_lines))
    helper = answers.get("helper") or {}
    helper_text = (f"The user's helper is {helper['name']}. Say \"{helper['name']}\" in messages, not \"your helper\"."
                   if helper.get("name") else "")
    text = set_slot(text, "helper", helper_text)
    text = set_slot(text, "other-ai", other_ai_text(answers.get("subscriptions") or []))
    text = re.sub(r"\n{3,}", "\n\n", text)
    agents_path.write_text(text, encoding="utf-8")

    written = []
    for skill in answers.get("skills", []):
        folder = root / ".claude" / "skills" / skill["name"]
        folder.mkdir(parents=True, exist_ok=True)
        description = " ".join(skill["description"].split())
        body = skill["body"].strip() + "\n"
        (folder / "SKILL.md").write_text(f"---\nname: {skill['name']}\ndescription: >\n  {description}\n---\n\n{body}",
                                         encoding="utf-8")
        written.append(str(folder.relative_to(root)).replace("\\", "/"))
    for f in folders:
        folder = root / f["name"]
        folder.mkdir(parents=True, exist_ok=True)
        if f.get("agents"):
            (folder / "AGENTS.md").write_text(f["agents"].strip() + "\n", encoding="utf-8")
            (folder / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
    profile = {"name": name, "plan": answers.get("plan", ""), "subscriptions": answers.get("subscriptions") or [],
               "helper": {"name": helper.get("name", "")}, "skills": [s["name"] for s in answers.get("skills", [])],
               "first_exploration": answers.get("first_exploration", "")}
    (root / ".kit").mkdir(exist_ok=True)
    (root / ".kit" / "profile.json").write_text(json.dumps(profile, indent=2) + "\n", encoding="utf-8")
    return {"agents": "AGENTS.md", "skills": written, "folders": [f["name"] for f in folders], "profile": ".kit/profile.json"}


def other_ai_text(subscriptions: list[str]) -> str:
    others = [s for s in subscriptions if s.lower() != "claude"]
    if not others:
        return ""
    names = {"chatgpt": "ChatGPT (Codex CLI)", "grok": "Grok (grok CLI)", "gemini": "Gemini (gemini CLI)"}
    listed = ", ".join(names.get(s.lower(), s) for s in others)
    return f"""## Other AI subscriptions

The user also pays for {listed}. CLIProxyAPI runs at logon on
`http://127.0.0.1:8317` as an agent-only route to those subscriptions.
Route child work through it when the task is long, bulky or repetitive
(research sweeps, bulk rewrites, first drafts, second-opinion reviews), so the
user's Claude limits last for the work only Claude should do. Keep anything
involving money, publishing or the user's accounts on Claude. Never show the
proxy or its config to the user, and never read its config folder.
"""
