"""Decision briefs and the glossary (D54). `kit explain` renders the fixed
shape; the explain skill fills it in the user's terms.
"""

from __future__ import annotations

import re
from pathlib import Path

from .common import KitError

BRIEF = """## {title}

**What I'm deciding.** {deciding}

**Your options.**
{options}

**What each costs you.**
{costs}

**What I recommend, and why.** {recommendation}

**What you'd have to do.** {action}
"""

GLOSSARY_ENTRY = "- **{term}**: {meaning}"
GLOSSARY_FILE = "GLOSSARY.md"


def brief_template(title: str = "<the decision in a few words>") -> str:
    return BRIEF.format(
        title=title,
        deciding="<one sentence: the question, in their words>",
        options="- <option A, one line>\n- <option B, one line>",
        costs="- <option A>: <time>, <money>, <risk>\n- <option B>: <time>, <money>, <risk>",
        recommendation="<the pick and the one reason that matters most to them>",
        action="<nothing / one click / a yes or no / a decision by a date>",
    )


def render_brief(data: dict) -> str:
    required = ("title", "deciding", "options", "costs", "recommendation", "action")
    missing = [k for k in required if not data.get(k)]
    if missing:
        raise KitError("a brief needs " + ", ".join(missing))
    options = data["options"] if isinstance(data["options"], str) else "\n".join(f"- {o}" for o in data["options"])
    costs = data["costs"] if isinstance(data["costs"], str) else "\n".join(f"- {c}" for c in data["costs"])
    return BRIEF.format(title=data["title"], deciding=data["deciding"], options=options, costs=costs,
                        recommendation=data["recommendation"], action=data["action"])


def glossary_terms(root: Path) -> dict[str, str]:
    path = root / GLOSSARY_FILE
    if not path.exists():
        return {}
    terms = {}
    for m in re.finditer(r"^- \*\*(.+?)\*\*: (.+)$", path.read_text(encoding="utf-8"), re.M):
        terms[m.group(1).strip().lower()] = m.group(2).strip()
    return terms


def glossary_add(root: Path, term: str, meaning: str) -> dict:
    path = root / GLOSSARY_FILE
    existing = glossary_terms(root)
    if term.strip().lower() in existing:
        return {"added": False, "term": term, "reason": "already in the glossary"}
    if not path.exists():
        path.write_text("# Glossary\n\nWords that came up, explained once. Claude adds a term the first time it uses it.\n\n",
                        encoding="utf-8")
    text = path.read_text(encoding="utf-8").rstrip("\n")
    entries = sorted(list(existing.items()) + [(term.strip().lower(), meaning.strip())])
    header = text.split("\n- **", 1)[0].rstrip("\n")
    body = "\n".join(GLOSSARY_ENTRY.format(term=t.capitalize() if t.islower() else t, meaning=m) for t, m in entries)
    path.write_text(f"{header}\n\n{body}\n", encoding="utf-8")
    return {"added": True, "term": term}
