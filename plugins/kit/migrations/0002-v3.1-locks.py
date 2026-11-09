"""v3.1 (2026-11-09, D80): workspaces made before v3.1 get the deny rules
that make destructive git and GitHub actions hard, and the two glossary
terms the locks use. Idempotent: adds only what is missing. The GitHub side
(squash-only, rulesets, safe points) is the `locks` chore's job, because a
migration runs offline."""

from __future__ import annotations

import json
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parents[1]

TERMS = {
    "Safe point": "A bookmark the caretaker leaves on your GitHub backup every morning, kept for 30 days. "
                  "If something goes wrong, say \"undo to yesterday\" and Claude puts the main copy back to it "
                  "without losing anything since; that step can itself be undone.",
    "Lock": "A rule on your GitHub backup that stops the main copy being erased or overwritten. Every helper "
            "is told no on every plan; on GitHub Pro, or a public repository, GitHub itself refuses too.",
}


def apply(root: Path) -> str:
    made = []
    settings = root / ".claude" / "settings.json"
    template = json.loads((KIT_ROOT / "template" / ".claude" / "settings.json").read_text(encoding="utf-8"))
    if settings.exists():
        try:
            data = json.loads(settings.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = None
        if isinstance(data, dict):
            deny = data.setdefault("permissions", {}).setdefault("deny", [])
            missing = [rule for rule in template["permissions"]["deny"] if rule not in deny]
            if missing:
                deny.extend(missing)
                settings.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
                made.append(f"{len(missing)} deny rules in .claude/settings.json")
    glossary = root / "GLOSSARY.md"
    if glossary.exists():
        text = glossary.read_text(encoding="utf-8")
        added = []
        for term, meaning in TERMS.items():
            if f"**{term}**" not in text:
                text = text.rstrip("\n") + f"\n- **{term}**: {meaning}\n"
                added.append(term)
        if added:
            glossary.write_text(text, encoding="utf-8")
            made.append("glossary: " + ", ".join(added))
    return "made " + ", ".join(made) if made else "nothing to do"
