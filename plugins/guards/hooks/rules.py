"""Decision rules for the guards plugin. Pure functions, no I/O, stdlib only.

Each check returns None when the action is fine, or a short plain-English
reason when it must be blocked. The reason is shown to Claude, which then
explains it to the user in its own words.
"""

from __future__ import annotations

import ntpath
import posixpath
import re
import shlex
import tempfile

# ---------------------------------------------------------------- splitting

_SEPARATORS = re.compile(r"(?:&&|\|\||;|\||\r?\n|`n)")
_WRAPPERS = {"sudo", "env", "command", "exec", "nohup", "time", "&", "."}


def split_segments(command: str) -> list[list[str]]:
    """Split a shell or PowerShell command line into word lists, one per
    simple command. Quotes are honored where possible; on a parse error the
    segment falls back to whitespace splitting, which errs toward blocking."""
    segments: list[list[str]] = []
    for raw in _SEPARATORS.split(command):
        raw = raw.strip().lstrip("({").rstrip(")}").strip()
        if not raw:
            continue
        # Windows paths use backslashes, which POSIX shlex would eat.
        raw = raw.replace("\\", "/")
        try:
            words = shlex.split(raw, posix=True)
        except ValueError:
            words = raw.split()
        # Look inside `bash -c "..."`, `powershell -Command "..."`, `cmd /c ...`.
        inner = _inner_command(words)
        if inner is not None:
            segments.extend(split_segments(inner))
            continue
        while words and words[0].lower() in _WRAPPERS:
            words = words[1:]
        if words:
            segments.append(words)
    return segments


def _inner_command(words: list[str]) -> str | None:
    if not words:
        return None
    exe = _basename(words[0]).lower().removesuffix(".exe")
    flags = {"bash": {"-c", "-lc"}, "sh": {"-c"}, "zsh": {"-c"},
             "powershell": {"-command", "-c"}, "pwsh": {"-command", "-c"},
             "cmd": {"/c", "/k"}}
    if exe not in flags:
        return None
    for i, w in enumerate(words[1:], start=1):
        if w.lower() in flags[exe] and i + 1 < len(words):
            return " ".join(words[i + 1:])
    return None


def _basename(word: str) -> str:
    return ntpath.basename(word.replace("/", "\\"))


# ---------------------------------------------------------------- git rules

def _git_args(words: list[str]) -> list[str] | None:
    """Return the git subcommand and its arguments, skipping global options
    such as `-C <dir>` and `-c key=value`. None when this is not git."""
    if not words or _basename(words[0]).lower().removesuffix(".exe") != "git":
        return None
    args = words[1:]
    while args and args[0].startswith("-"):
        opt = args.pop(0)
        if opt in ("-C", "-c", "--git-dir", "--work-tree", "--namespace") and args:
            args.pop(0)
    return args


def check_git(command: str) -> str | None:
    for words in split_segments(command):
        args = _git_args(words)
        if not args:
            continue
        sub, rest = args[0], args[1:]
        flags = [a for a in rest if a.startswith("-")]
        plain = [a for a in rest if not a.startswith("-")]

        if sub == "reset" and "--hard" in rest:
            return "git reset --hard throws away unsaved work. Make a new commit instead, or ask the user first."
        if sub == "clean" and any(f == "--force" or (not f.startswith("--") and "f" in f) for f in flags):
            return "git clean -f deletes files that were never saved in git. Ask the user before removing files."
        if sub == "branch" and ("-D" in rest or ("--delete" in rest and "--force" in rest)):
            return "git branch -D deletes a branch even if its work isn't merged. Use git branch -d, which refuses when work would be lost."
        if sub == "checkout" and ("." in plain or "-f" in flags or "--force" in flags):
            return "git checkout . throws away unsaved changes. Commit them first, or ask the user."
        if sub == "restore" and "." in plain:
            return "git restore . throws away unsaved changes. Commit them first, or ask the user."
        if sub == "push":
            if any(f in ("-f", "--force", "--force-with-lease", "--force-if-includes", "--mirror", "--delete", "-d") or f.startswith("--force-with-lease=") for f in flags):
                return "Force pushes and remote deletes can erase the backup on GitHub, so they're blocked here."
            if any(p.startswith("+") or p.startswith(":") for p in plain[1:]):
                return "This push would overwrite or delete history on GitHub, so it's blocked here."
            if plain and plain[0] != "origin":
                return f"Pushes go only to origin. '{plain[0]}' is a different place, so this push is blocked."
    return None


# ---------------------------------------------------------------- delete rules

_DELETE_COMMANDS = {"rm", "rmdir", "del", "erase", "rd", "remove-item", "ri", "unlink", "shred"}
_PS_PATH_PARAMS = {"-path", "-literalpath", "-lp"}


def _norm(path: str) -> str:
    return path.replace("\\", "/").rstrip("/").lower()


def _is_within(path: str, root: str) -> bool:
    p, r = _norm(path), _norm(root)
    return p == r or p.startswith(r + "/")


def _resolve(target: str, cwd: str) -> str:
    target = target.strip("'\"")
    home_like = target.startswith("~") or target.lower().startswith(("$home", "$env:userprofile", "%userprofile%"))
    if home_like:
        return "~home~/" + target
    windows = bool(re.match(r"^[a-zA-Z]:", cwd)) or "\\" in cwd
    mod = ntpath if windows else posixpath
    if mod.isabs(target) or re.match(r"^[a-zA-Z]:", target):
        return mod.normpath(target)
    return mod.normpath(mod.join(cwd, target))


def check_delete(command: str, cwd: str, project_dir: str) -> str | None:
    temp = tempfile.gettempdir()
    for words in split_segments(command):
        exe = _basename(words[0]).lower().removesuffix(".exe")
        if exe not in _DELETE_COMMANDS:
            continue
        targets: list[str] = []
        args = words[1:]
        i = 0
        while i < len(args):
            a = args[i]
            if a.lower() in _PS_PATH_PARAMS and i + 1 < len(args):
                targets.extend(t for t in args[i + 1].split(",") if t)
                i += 2
                continue
            if not a.startswith("-") and not (a.startswith("/") and len(a) <= 3 and exe in {"del", "erase", "rd", "rmdir"}):
                targets.append(a)
            i += 1
        for t in targets:
            resolved = _resolve(t, cwd)
            if resolved.startswith("~home~"):
                return f"Deleting '{t}' reaches outside the workspace, so it's blocked."
            if _is_within(resolved, project_dir) and _norm(resolved) != _norm(project_dir):
                continue
            if _is_within(resolved, temp):
                continue
            return f"Deleting '{t}' reaches outside the workspace, so it's blocked. Ask the user first."
    return None


# ---------------------------------------------------------------- secret rules

_SAFE_SUFFIXES = (".example", ".sample", ".template", ".dist", ".pub")
_SECRET_PATTERNS = [
    re.compile(p) for p in (
        r"(^|/)\.env($|\.[^/]*$)",
        r"\.(pem|key|p12|pfx|jks|keystore|1pux|kdbx)$",
        r"(^|/)id_(rsa|dsa|ecdsa|ed25519)$",
        r"(^|/)\.ssh/",
        r"(^|/)\.git-credentials$",
        r"(^|/)\.netrc$",
        r"(^|/)credentials(\.json)?$",
        r"(^|/)secrets?(/|$|\.json$|\.ya?ml$|\.toml$)",
        r"(^|/)bitwarden_export[^/]*\.(json|csv)$",
        r"(^|/)\.cli-proxy-api/",
        r"(^|/)\.config/gh/hosts\.yml$",
    )
]


def is_secret_path(path: str) -> bool:
    p = _norm(path)
    if not p or p.endswith(_SAFE_SUFFIXES):
        return False
    return any(rx.search(p) for rx in _SECRET_PATTERNS)


_SECRET_REASON = ("'{0}' looks like a secret file (passwords, keys or tokens). Agents never read or change those. "
                  "If a secret is needed, use a 1Password reference (op://...) with `op run`.")


def check_secret_command(command: str) -> str | None:
    for words in split_segments(command):
        for w in words[1:]:
            for piece in re.split(r"[=,]", w):
                if is_secret_path(piece.strip("'\"")):
                    return _SECRET_REASON.format(piece)
    return None


def check_tool(tool_name: str, tool_input: dict, cwd: str, project_dir: str) -> str | None:
    """Route one PreToolUse event to the rules that apply."""
    if tool_name in ("Bash", "PowerShell"):
        cmd = str(tool_input.get("command", ""))
        return check_git(cmd) or check_delete(cmd, cwd, project_dir) or check_secret_command(cmd)
    if tool_name in ("Read", "Edit", "Write", "MultiEdit", "NotebookEdit"):
        path = str(tool_input.get("file_path") or tool_input.get("notebook_path") or "")
        return _SECRET_REASON.format(path) if is_secret_path(path) else None
    if tool_name in ("Grep", "Glob"):
        for key in ("path", "pattern", "glob"):
            value = str(tool_input.get(key) or "")
            if value and is_secret_path(value):
                return _SECRET_REASON.format(value)
    return None
