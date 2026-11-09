"""Migrations (D72): a release may carry one. `kit migrate` runs every pending
migration once, in order, and logs it in .kit/migrations.json. Each migration
is plugins/kit/migrations/NNNN-<name>.py with `apply(root: Path) -> str`;
it must be idempotent, because a half-run session may call it again.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from .common import KIT_ROOT, KitError, now_iso, read_json, write_json

MIGRATIONS = KIT_ROOT / "migrations"
STATE = Path(".kit") / "migrations.json"


def available() -> list[Path]:
    return sorted(p for p in MIGRATIONS.glob("[0-9][0-9][0-9][0-9]-*.py")) if MIGRATIONS.exists() else []


def load(root: Path) -> dict:
    return read_json(root / STATE, {"schema": "beep-beginners/migrations/v1", "applied": {}})


def pending(root: Path) -> list[Path]:
    applied = load(root)["applied"]
    return [p for p in available() if p.stem not in applied]


def run(root: Path, dry_run: bool = False) -> dict:
    state = load(root)
    results = []
    for path in pending(root):
        if dry_run:
            results.append({"migration": path.stem, "applied": False, "dry_run": True})
            continue
        spec = importlib.util.spec_from_file_location(f"kit_migration_{path.stem.replace('-', '_')}", path)
        if spec is None or spec.loader is None:
            raise KitError(f"cannot load migration {path.name}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        note = module.apply(root)
        state["applied"][path.stem] = {"at": now_iso(), "note": str(note or "")}
        write_json(root / STATE, state)
        results.append({"migration": path.stem, "applied": True, "note": str(note or "")})
    return {"ran": results, "pending_before": len(results), "applied_total": len(state["applied"])}
