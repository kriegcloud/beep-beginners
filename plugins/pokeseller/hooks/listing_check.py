# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Check a listing draft against the folder's listing-rules.toml.

  listing_check.py <draft.md>     check one draft and print the problems
  (as a PostToolUse hook)         reads the event on stdin; checks drafts under
                                  a listings/ folder; exit 2 sends problems back
                                  to Claude so it fixes the draft

A draft is a text file with "Field: value" lines (Title, Condition, Price,
Shipping) and a "Description:" line followed by the description text.
"""

from __future__ import annotations

import json
import re
import sys
import tomllib
from pathlib import Path

JAPANESE = re.compile(r"[぀-ヿㇰ-ㇿ㐀-䶿一-鿿ｦ-ﾟ]")
GRADED = re.compile(r"\b(PSA|CGC|BGS|SGC|TAG|ACE)\b\s*\d|\bgraded\b|\bslab\b", re.I)
DEFAULT_RULES = {
    "title_max": 80,
    "no_japanese": True,
    "price_must_be_empty": True,
    "cert_number_pattern": r"\b(cert(ification)?\s*(#|no\.?|number)?\s*:?\s*)?\d{7,10}\b",
    "graded": {"condition": "Good", "shipping_line": ""},
}


def parse_draft(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    lines = text.splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"^\s*(?:[-*]\s*)?\**([A-Za-z ]+?)\**\s*:\s*(.*)$", line)
        if not m:
            continue
        key = m.group(1).strip().lower()
        if key == "description":
            fields["description"] = "\n".join([m.group(2), *lines[i + 1:]]).strip()
            break
        fields[key] = m.group(2).strip()
    return fields


def load_rules(draft: Path) -> dict:
    for folder in [draft.parent, *draft.parents]:
        candidate = folder / "listing-rules.toml"
        if candidate.exists():
            with candidate.open("rb") as fh:
                loaded = tomllib.load(fh)
            merged = {**DEFAULT_RULES, **loaded}
            merged["graded"] = {**DEFAULT_RULES["graded"], **loaded.get("graded", {})}
            return merged
    return DEFAULT_RULES


def check(fields: dict[str, str], rules: dict) -> list[str]:
    problems: list[str] = []
    title = fields.get("title", "")
    description = fields.get("description", "")
    everything = "\n".join(fields.values())
    if not title:
        problems.append("The draft has no Title line.")
    elif len(title) > int(rules["title_max"]):
        problems.append(f"The title is {len(title)} characters; Mercari allows {rules['title_max']}.")
    if rules.get("no_japanese") and JAPANESE.search(everything):
        problems.append("The draft has Japanese characters. Use the English card name and write 'Japanese' in words.")
    pattern = rules.get("cert_number_pattern")
    if pattern and re.search(pattern, f"{title}\n{description}", re.I):
        problems.append("The draft seems to include a grading cert number. Leave it out of the title and description.")
    if rules.get("price_must_be_empty") and fields.get("price", "").strip():
        problems.append("The price is filled in. Leave it empty; the seller sets it.")
    if GRADED.search(f"{title}\n{description}"):
        want = rules["graded"].get("condition")
        if want and fields.get("condition", "").strip().lower() != want.lower():
            problems.append(f"Graded slabs use condition '{want}'.")
        line = rules["graded"].get("shipping_line")
        if line and line.lower() not in everything.lower():
            problems.append(f"Graded slabs need the shipping line: \"{line}\"")
    return problems


def check_file(path: Path) -> list[str]:
    return check(parse_draft(path.read_text(encoding="utf-8")), load_rules(path))


def is_draft(path: str) -> bool:
    p = path.replace("\\", "/").lower()
    return "/listings/" in p and p.endswith((".md", ".txt"))


def main() -> int:
    if len(sys.argv) > 1:
        problems = check_file(Path(sys.argv[1]))
        print("\n".join(problems) if problems else "OK: the draft follows the listing rules.")
        return 1 if problems else 0
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    path = str((event.get("tool_input") or {}).get("file_path", ""))
    if not path or not is_draft(path) or not Path(path).exists():
        return 0
    problems = check_file(Path(path))
    if problems:
        print("The listing draft breaks the listing rules. Fix these, then save it again:\n- "
              + "\n- ".join(problems), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
