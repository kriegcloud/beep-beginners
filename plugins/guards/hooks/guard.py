# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""PreToolUse guard: git safety, deletes outside the workspace, secret files.

Reads the hook event from stdin. Exit 0 lets the tool run. Exit 2 blocks it,
and stderr tells Claude why. Never answers "ask", because auto mode ignores it.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rules import check_tool  # noqa: E402


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        print("Guard could not read the tool request, so it was blocked to be safe.", file=sys.stderr)
        return 2
    cwd = str(event.get("cwd") or os.getcwd())
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR") or cwd
    reason = check_tool(str(event.get("tool_name", "")), event.get("tool_input") or {}, cwd, project_dir)
    if reason:
        print(f"Blocked by the workspace guard: {reason}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
