# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest>=8"]
# ///
"""Run: uv run --script plugins/pokeseller/tests/test_listing_check.py"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "hooks"))
from listing_check import check_file  # noqa: E402

GOOD = """Title: Arcanine 2023 Japanese Pokemon 151 PSA 8
Condition: Good
Price:
Description:
Graded PSA 8 NM-MT
Slab ships in a bubble mailer with protection.
"""


@pytest.fixture()
def folder(tmp_path: Path) -> Path:
    shutil.copy(HERE.parent / "listing-rules.example.toml", tmp_path / "listing-rules.toml")
    (tmp_path / "listings").mkdir()
    return tmp_path / "listings"


def write(folder: Path, text: str) -> Path:
    path = folder / "draft.md"
    path.write_text(text, encoding="utf-8")
    return path


def test_good_draft(folder: Path) -> None:
    assert check_file(write(folder, GOOD)) == []


@pytest.mark.parametrize("bad,expected", [
    (GOOD.replace("Arcanine", "Arcanine (ウィンディ)"), "Japanese characters"),
    (GOOD.replace("Graded PSA 8 NM-MT", "Graded PSA 8 NM-MT cert 84512367"), "cert number"),
    (GOOD.replace("Price:", "Price: 45"), "price is filled"),
    (GOOD.replace("Condition: Good", "Condition: Like new"), "condition 'Good'"),
    (GOOD.replace("Slab ships in a bubble mailer with protection.", ""), "shipping line"),
    (GOOD.replace("Title: Arcanine", "Title: " + "A" * 90), "characters; Mercari allows 80"),
])
def test_bad_drafts(folder: Path, bad: str, expected: str) -> None:
    problems = check_file(write(folder, bad))
    assert any(expected in p for p in problems), problems


def test_raw_card_skips_graded_rules(folder: Path) -> None:
    raw = "Title: Pikachu 2016 Evolutions Holo\nCondition: Near mint\nPrice:\nDescription:\nRaw card, sleeved.\n"
    assert check_file(write(folder, raw)) == []


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
