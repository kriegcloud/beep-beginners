"""v3.2 (2026-11-09, D82): frontmatter that standard YAML readers reject.

Before v3.2 the template's docs/agents/issue-tracker.md carried an unquoted
`title: Issue tracker: local markdown ...`, and the kit's forgiving reader let
pages like it through. okflint, Obsidian and OpenKnowledge's own parser do not.
This quotes, in place, each value `kit docs validate` flags as E7, and
changes nothing else on the page: frontmatter comments, key order, spacing
and the body stay byte for byte. A page that isn't valid UTF-8 is never
rewritten; it is reported instead. Idempotent: a page with no E7 problem is
left alone.
"""

from __future__ import annotations

import sys
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KIT_ROOT / "scripts"))

from kitlib import okf  # noqa: E402


def _candidates(root: Path) -> list[Path]:
    found = []
    if (root / "docs").exists():
        found += [p for p in (root / "docs").rglob("*.md") if ".git" not in p.parts]
    for hub in ("explorations", "goals"):
        if (root / hub).exists():
            found += sorted((root / hub).glob("*/README.md"))
    if (root / "GLOSSARY.md").exists():
        found.append(root / "GLOSSARY.md")
    return found


def apply(root: Path) -> str:
    fixed, unreadable = [], []
    for path in _candidates(root):
        rel = path.relative_to(root).as_posix()
        if not okf.strict_yaml_problems(path.read_text(encoding="utf-8", errors="replace")):
            continue
        try:
            text = path.read_bytes().decode("utf-8")  # bytes, so CRLF line endings survive
        except UnicodeDecodeError:
            unreadable.append(rel)
            continue
        new = okf.quote_problem_values(text)
        if new != text:
            path.write_bytes(new.encode("utf-8"))
            fixed.append(rel)
    notes = []
    if fixed:
        notes.append(f"quoted frontmatter values in {len(fixed)} page(s): {', '.join(fixed)}")
    if unreadable:
        notes.append(f"left {len(unreadable)} page(s) that aren't UTF-8 for a person to check: {', '.join(unreadable)}")
    return "; ".join(notes) if notes else "nothing to quote"
