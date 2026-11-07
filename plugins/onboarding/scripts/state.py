# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Onboarding progress, so setup can stop anywhere and pick up where it left off.

  state.py show                          the whole state (JSON)
  state.py next                          the first step not done yet
  state.py done <step> [--note TEXT]     mark a step done
  state.py skip <step> --note TEXT       mark a step skipped, with the reason
  state.py answer <key> <json-value>     store an answer, e.g. answer subscriptions '["claude"]'
  state.py reset                         start over (keeps a backup copy)

The state lives in ~/.beep-beginners/onboarding.json (override with
BEEP_BEGINNERS_STATE). It never holds passwords, tokens or keys.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import sys
from pathlib import Path

STEPS = [
    ("bootstrap", "Claude Code, the kit and this setup are installed"),
    ("detect", "Look at what this computer already has"),
    ("chrome", "Claude in Chrome is installed and connected"),
    ("questions", "Your accounts, subscriptions and what you want"),
    ("install-user", "Install the apps that don't need permission"),
    ("install-machine", "Install the rest, behind one Windows permission prompt"),
    ("signin-github", "Sign in to GitHub"),
    ("signin-claude-cli", "Sign in to Claude Code"),
    ("signin-1password", "Sign in to 1Password and turn on its Claude connection"),
    ("passwords", "Move your passwords from Bitwarden into 1Password"),
    ("github-key", "Give this computer a key for GitHub"),
    ("location", "Pick where your workspace lives"),
    ("workspace", "Create your private workspace on GitHub"),
    ("signin-tailscale", "Sign in to Tailscale"),
    ("remote-help", "Set up the help line to your helper"),
    ("other-ai", "Set up your other AI subscriptions"),
    ("verify", "Check that every app works"),
    ("welcome", "Say hello and show what you can do"),
]


def state_dir() -> Path:
    folder = Path(os.environ.get("BEEP_BEGINNERS_STATE") or Path.home() / ".beep-beginners")
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def state_file() -> Path:
    return state_dir() / "onboarding.json"


def now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def load_state() -> dict:
    path = state_file()
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            shutil.copy(path, path.with_suffix(".broken.json"))
    return {"schema": "beep-beginners/onboarding/v1", "started": now(), "steps": {}, "answers": {}}


def save_state(state: dict) -> None:
    state["updated"] = now()
    tmp = state_file().with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    tmp.replace(state_file())


def next_step(state: dict) -> dict:
    for step, label in STEPS:
        if state["steps"].get(step, {}).get("status") not in ("done", "skipped"):
            return {"step": step, "label": label,
                    "done": [s for s, _ in STEPS if state["steps"].get(s, {}).get("status") == "done"]}
    return {"step": None, "label": "Setup is finished."}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("show")
    sub.add_parser("next")
    for name in ("done", "skip"):
        p = sub.add_parser(name)
        p.add_argument("step", choices=[s for s, _ in STEPS])
        p.add_argument("--note", required=(name == "skip"))
    p = sub.add_parser("answer"); p.add_argument("key"); p.add_argument("value")
    sub.add_parser("reset")
    args = parser.parse_args()

    state = load_state()
    if args.cmd == "show":
        print(json.dumps(state, indent=2))
        return 0
    if args.cmd == "reset":
        if state_file().exists():
            shutil.copy(state_file(), state_dir() / f"onboarding.{dt.datetime.now():%Y%m%d-%H%M%S}.json")
            state_file().unlink()
        print(json.dumps({"reset": True}))
        return 0
    if args.cmd in ("done", "skip"):
        state["steps"][args.step] = {"status": "done" if args.cmd == "done" else "skipped",
                                     "at": now(), **({"note": args.note} if args.note else {})}
    elif args.cmd == "answer":
        try:
            state["answers"][args.key] = json.loads(args.value)
        except json.JSONDecodeError:
            state["answers"][args.key] = args.value
    save_state(state)
    print(json.dumps(next_step(state), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
