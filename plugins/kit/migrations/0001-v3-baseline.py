"""v3 baseline (2026-11-08): workspaces made before v3 get the files v3 expects.
Idempotent: every step checks before it writes."""

from __future__ import annotations

import json
from pathlib import Path


def apply(root: Path) -> str:
    made = []
    kit = root / ".kit"
    kit.mkdir(exist_ok=True)
    for name, data in (("chores.json", {"schema": "beep-beginners/chores/v1", "last": {}}),):
        path = kit / name
        if not path.exists():
            path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            made.append(f".kit/{name}")
    for folder in ("projects", "docs/lessons"):
        if not (root / folder).exists():
            (root / folder).mkdir(parents=True)
            made.append(folder + "/")
    needs = root / "NEEDS-YOU.md"
    if not needs.exists():
        needs.write_text("# Needs you\n\nThe caretaker keeps this page.\n\n## Needs you\n\nNothing right now.\n\n"
                         "## This week\n\nNo weekly note yet.\n\n## Done lately\n\nNothing yet.\n", encoding="utf-8")
        made.append("NEEDS-YOU.md")
    glossary = root / "GLOSSARY.md"
    if glossary.exists() and not glossary.read_text(encoding="utf-8").startswith("---"):
        glossary.write_text("---\ntype: glossary\ntitle: Glossary\ndescription: \"Words that came up, explained once.\"\nstatus: stable\n---\n"
                            + glossary.read_text(encoding="utf-8"), encoding="utf-8")
        made.append("GLOSSARY.md frontmatter")
    old = root / "CHANGELOG-FOR-ED.md"
    if old.exists():
        old.unlink()
        made.append("removed CHANGELOG-FOR-ED.md (now WHAT-CHANGED.md, regenerated)")
    return "made " + ", ".join(made) if made else "nothing to do"
