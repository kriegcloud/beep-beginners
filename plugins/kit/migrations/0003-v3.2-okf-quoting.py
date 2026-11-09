"""v3.2 (2026-11-09, D82): frontmatter that standard YAML readers reject.

Before v3.2 the template's docs/agents/issue-tracker.md carried an unquoted
`title: Issue tracker: local markdown ...`, and the kit's forgiving reader let
pages like it through. okflint, Obsidian and OpenKnowledge's own parser do not.
This rewrites the frontmatter of any page that `kit docs validate` flags as E7,
through the kit's writer, which quotes such values. Bodies are untouched.
Idempotent: a page with no E7 problem is left alone.
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
    fixed = []
    for path in _candidates(root):
        text = path.read_text(encoding="utf-8", errors="replace")
        if not okf.strict_yaml_problems(text):
            continue
        meta, body = okf.split_frontmatter(text)
        if meta is None:
            continue
        okf.write(path, meta, body)
        fixed.append(path.relative_to(root).as_posix())
    return f"quoted frontmatter values in {len(fixed)} page(s): {', '.join(fixed)}" if fixed else "nothing to quote"
