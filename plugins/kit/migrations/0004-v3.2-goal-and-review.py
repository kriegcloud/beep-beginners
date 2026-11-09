"""v3.2 (2026-11-09, D83, D84): goals run through Claude Code's `/goal`, and
the review before landing is Matt Pocock's, named in full.

- Every goal packet without a `GOAL.md` gets one from the kit's template, so
  `/goal follow the instructions in ./goals/<slug>/GOAL.md` works on goals
  made before v3.2.
- The workspace's `AGENTS.md` and each project's `AGENTS.md` swap the old
  lines (the retired `goal` skill, a bare `code-review`) for the new ones,
  only where the old text is still there word for word. A line the user or an
  agent has since reworded is left alone.

Idempotent: it writes nothing a second time.
"""

from __future__ import annotations

import json
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parents[1]

ROOT_SWAPS = [
    ("- `goals/` holds work that graduated from an exploration (`goal` skill).",
     "- `goals/` holds work that graduated from an exploration. The `make-goal`\n"
     "  skill makes the packet; `/goal follow the instructions in ./goals/<slug>/GOAL.md`\n"
     "  works it."),
    ("- `tdd` while building. `code-review` before the branch lands; findings are\n"
     "  fixed, or waived with a reason written in the packet.",
     "- `tdd` while building. `mattpocock-skills:code-review` (named in full; a\n"
     "  bare `code-review` is Claude Code's built-in) before the branch lands;\n"
     "  findings are fixed, or waived with a reason written in the packet."),
]
PROJECT_SWAPS = [
    ("- While building: `tdd`. Before landing: `code-review`, findings fixed or\n  waived in the packet.",
     "- While building: `tdd`. Before landing: `mattpocock-skills:code-review`\n"
     "  (named in full), findings fixed or waived in the packet."),
]


def _swap(path: Path, swaps: list[tuple[str, str]]) -> bool:
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    new = text
    for old, replacement in swaps:
        new = new.replace(old, replacement)
    if new == text:
        return False
    path.write_text(new, encoding="utf-8")
    return True


def apply(root: Path) -> str:
    made, swapped = [], []
    template = (KIT_ROOT / "templates" / "goal" / "GOAL.md").read_text(encoding="utf-8")
    for state_file in sorted((root / "goals").glob("*/.packet.json")) if (root / "goals").exists() else []:
        folder = state_file.parent
        if (folder / "GOAL.md").exists():
            continue
        try:
            title = json.loads(state_file.read_text(encoding="utf-8")).get("title") or folder.name
        except json.JSONDecodeError:
            title = folder.name
        (folder / "GOAL.md").write_text(template.replace("{{title}}", title).replace("{{slug}}", folder.name),
                                        encoding="utf-8")
        made.append(folder.name)
    if _swap(root / "AGENTS.md", ROOT_SWAPS):
        swapped.append("AGENTS.md")
    for agents in sorted((root / "projects").glob("*/AGENTS.md")) if (root / "projects").exists() else []:
        if _swap(agents, PROJECT_SWAPS):
            swapped.append(agents.relative_to(root).as_posix())
    parts = []
    if made:
        parts.append(f"GOAL.md for {len(made)} goal(s): {', '.join(made)}")
    if swapped:
        parts.append(f"updated {', '.join(swapped)}")
    return "; ".join(parts) if parts else "nothing to change"
