"""docs/ as an Open Knowledge Format v0.2 bundle (D60, D61, D64, D71).

One concept per markdown file with YAML frontmatter. `type` is required; the
kit also writes `title`, `description`, `sources`, `generated`, `verified`,
`status` and `stale_after`. Frontmatter is read and written with a small
block-style YAML subset (what the kit itself writes, plus flow mappings and
quoted scalars), because hooks and the sandbox must stay standard library.

Ownership (D60 question): `.packet.json` owns a packet's lifecycle (active,
parked, graduated, stage, open questions). A packet README's frontmatter owns
only the OKF trust fields and mirrors description and dates from the state
file; `packets.py` rewrites it on every state change.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import shutil
import tempfile
from pathlib import Path

from .common import KIT_ROOT, KitError, now_iso, run, slugify

RESERVED = {"index.md", "log.md"}
STATUSES = ("draft", "stable", "deprecated")
EXPORT_TYPES = ("preference", "business-fact", "workflow", "correction", "lesson")  # D71 allowlist

# D61 defaults, in days. None means never stale.
STALE_DAYS = {
    "how-to": 90, "tool-fact": 90, "workflow": 90,
    "preference": 180, "profile-fact": 180,
    "business-fact": 30, "money-fact": 30, "account-fact": 30,
    "decision": None, "lesson": None, "correction": 180,
    "exploration": 30, "goal": 30, "glossary": None, "agent-config": None,
}

KIT_ACTOR = "process:kit"


# ---------------------------------------------------------------- yaml subset

def _scalar(text: str):
    text = text.strip()
    if text == "" or text in ("null", "~"):
        return None
    if len(text) >= 2 and text.startswith("'") and text.endswith("'"):
        return text[1:-1].replace("''", "'")
    if len(text) >= 2 and text.startswith('"') and text.endswith('"'):
        return re.sub(r'\\(["\\])', r"\1", text[1:-1])
    if text in ("true", "false"):
        return text == "true"
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    if text.startswith("[") and text.endswith("]"):
        inner = text[1:-1].strip()
        return [_scalar(p) for p in _split_flow(inner)] if inner else []
    if text.startswith("{") and text.endswith("}"):
        inner = text[1:-1].strip()
        out = {}
        for part in _split_flow(inner):
            k, _, v = part.partition(":")
            out[k.strip()] = _scalar(v)
        return out
    return text


def _split_flow(text: str) -> list[str]:
    parts, depth, cur, quote = [], 0, "", None
    for ch in text:
        if quote:
            cur += ch
            if ch == quote:
                quote = None
            continue
        if ch in "\"'":
            quote = ch
        elif ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    if cur.strip():
        parts.append(cur)
    return parts


def parse_yaml(text: str) -> dict:
    """Block-style mappings, lists of scalars or mappings, flow scalars. Enough
    for OKF frontmatter as the kit and most agents write it."""
    lines = [ln.rstrip("\n") for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    pos = 0

    def indent_of(ln: str) -> int:
        return len(ln) - len(ln.lstrip(" "))

    def parse_block(indent: int):
        nonlocal pos
        if pos >= len(lines):
            return {}
        if lines[pos].lstrip().startswith("- "):
            return parse_list(indent_of(lines[pos]))
        result: dict = {}
        while pos < len(lines):
            ln = lines[pos]
            ind = indent_of(ln)
            if ind < indent:
                break
            if ind > indent:
                raise KitError(f"frontmatter: unexpected indent at: {ln.strip()!r}")
            if ln.lstrip().startswith("- "):
                break
            key, sep, value = ln.strip().partition(":")
            if not sep:
                raise KitError(f"frontmatter: expected 'key: value' at: {ln.strip()!r}")
            pos += 1
            if value.strip():
                result[key.strip()] = _scalar(value)
            elif pos < len(lines) and indent_of(lines[pos]) > ind:
                result[key.strip()] = parse_block(indent_of(lines[pos]))
            elif pos < len(lines) and indent_of(lines[pos]) == ind and lines[pos].lstrip().startswith("- "):
                result[key.strip()] = parse_list(ind)
            else:
                result[key.strip()] = None
        return result

    def parse_list(indent: int):
        nonlocal pos
        items = []
        while pos < len(lines):
            ln = lines[pos]
            ind = indent_of(ln)
            if ind != indent or not ln.lstrip().startswith("- "):
                break
            body = ln.strip()[2:]
            pos += 1
            if ":" in body and not body.startswith(("[", "{", '"', "'")):
                key, _, value = body.partition(":")
                item = {key.strip(): _scalar(value)}
                while pos < len(lines) and indent_of(lines[pos]) > indent and not lines[pos].lstrip().startswith("- "):
                    k, _, v = lines[pos].strip().partition(":")
                    pos += 1
                    if v.strip():
                        item[k.strip()] = _scalar(v)
                    elif pos < len(lines) and indent_of(lines[pos]) > indent_of(lines[pos - 1]):
                        item[k.strip()] = parse_block(indent_of(lines[pos]))
                    else:
                        item[k.strip()] = None
                items.append(item)
            else:
                items.append(_scalar(body))
        return items

    return parse_block(indent_of(lines[0])) if lines else {}


def _dump_scalar(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    text = str(value)
    if text == "" or re.search(r"[:#\[\]{},\"'\n]|^\s|\s$|^[-?&*!|>%@`]", text) or text in ("true", "false", "null", "~") or re.fullmatch(r"-?\d+(\.\d+)?", text):
        if "\\" in text and "'" not in text:
            return "'" + text + "'"  # YAML reads backslashes literally only in single quotes
        return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return text


def dump_yaml(data: dict, indent: int = 0) -> str:
    out: list[str] = []
    pad = " " * indent
    for key, value in data.items():
        if isinstance(value, dict):
            out.append(f"{pad}{key}:")
            out.append(dump_yaml(value, indent + 2))
        elif isinstance(value, list):
            if not value:
                out.append(f"{pad}{key}: []")
                continue
            out.append(f"{pad}{key}:")
            for item in value:
                if isinstance(item, dict):
                    first = True
                    for k, v in item.items():
                        prefix = f"{pad}  - " if first else f"{pad}    "
                        first = False
                        if isinstance(v, (dict, list)):
                            out.append(f"{prefix}{k}:")
                            out.append(dump_yaml({k: v}, indent + 4).split("\n", 1)[1] if isinstance(v, dict) else dump_yaml({k: v}, indent + 4).split("\n", 1)[1])
                        else:
                            out.append(f"{prefix}{k}: {_dump_scalar(v)}")
                else:
                    out.append(f"{pad}  - {_dump_scalar(item)}")
        else:
            out.append(f"{pad}{key}: {_dump_scalar(value)}")
    return "\n".join(line for line in out if line != "")


# ---------------------------------------------------------------- files

def split_frontmatter(text: str) -> tuple[dict | None, str]:
    if not text.startswith("---\n") and not text.startswith("---\r\n"):
        return None, text
    end = re.search(r"\n---[ \t]*\r?(\n|$)", text[3:])
    if not end:
        return None, text
    raw = text[4:3 + end.start() + 1]
    body = text[3 + end.end():]
    return parse_yaml(raw), body


def join_frontmatter(meta: dict, body: str) -> str:
    return f"---\n{dump_yaml(meta)}\n---\n{body.lstrip(chr(10))}"


def read(path: Path) -> tuple[dict | None, str]:
    return split_frontmatter(path.read_text(encoding="utf-8"))


def write(path: Path, meta: dict, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(join_frontmatter(meta, body), encoding="utf-8")


def stale_after_for(ctype: str, from_time: dt.datetime | None = None) -> str | None:
    days = STALE_DAYS.get(ctype, 90)
    if days is None:
        return None
    base = from_time or dt.datetime.now(dt.timezone.utc)
    return (base + dt.timedelta(days=days)).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def trust_tier(meta: dict) -> str:
    verified = meta.get("verified")
    if not verified:
        return "unverified"
    if isinstance(verified, dict):
        verified = [verified]
    if any(str(v.get("by", "")).startswith("human:") for v in verified if isinstance(v, dict)):
        return "human-reviewed"
    return "machine-confirmed"


def is_stale(meta: dict, now: dt.datetime | None = None) -> bool:
    value = meta.get("stale_after")
    if not value:
        return False
    try:
        when = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return False
    now = now or dt.datetime.now(dt.timezone.utc)
    if when.tzinfo is None:
        when = when.replace(tzinfo=dt.timezone.utc)
    return now >= when


# ---------------------------------------------------------------- concepts

def concept_files(folder: Path) -> list[Path]:
    return sorted(p for p in folder.rglob("*.md") if p.name not in RESERVED and ".git" not in p.parts)


def concept_new(root: Path, folder: str, title: str, ctype: str, body: str, description: str = "",
                sources: list[dict] | None = None, by: str = KIT_ACTOR, status: str = "draft",
                export: bool = False) -> dict:
    if export and ctype not in EXPORT_TYPES:
        raise KitError(f"a session may only export these concept types: {', '.join(EXPORT_TYPES)}")
    if status not in STATUSES:
        raise KitError(f"status must be one of {', '.join(STATUSES)}")
    base = root / "docs" / folder if folder else root / "docs"
    slug = slugify(title)
    path, n = base / f"{slug}.md", 2
    while path.exists():
        path, n = base / f"{slug}-{n}.md", n + 1
    meta: dict = {"type": ctype, "title": title, "description": description or title}
    if sources:
        meta["sources"] = sources
    meta["generated"] = {"by": by, "at": now_iso().replace("+00:00", "Z")}
    meta["status"] = status
    stale = stale_after_for(ctype)
    if stale:
        meta["stale_after"] = stale
    write(path, meta, body.strip() + "\n")
    rel = path.relative_to(root).as_posix()
    log_append(base, f"**Creation** {title} (`{rel}`), {status}, by {by}.")
    write_indexes(root)
    return {"path": rel, "id": rel[:-3], "status": status, "stale_after": stale}


def _find(root: Path, concept_id: str) -> Path:
    """Accept `docs/x.md`, `docs/x`, `x.md` or `x` (looked up under docs/)."""
    name = concept_id if concept_id.endswith(".md") else concept_id + ".md"
    for candidate in (root / name, root / "docs" / name):
        if candidate.exists():
            return candidate
    raise KitError(f"no page at {concept_id} (ids look like docs/<name> or just <name>)")


def verify(root: Path, concept_id: str, by: str, note: str = "") -> dict:
    path = _find(root, concept_id)
    meta, body = read(path)
    if meta is None:
        raise KitError(f"{concept_id} has no frontmatter")
    entry = {"by": by, "at": now_iso().replace("+00:00", "Z")}
    existing = meta.get("verified") or []
    if isinstance(existing, dict):
        existing = [existing]
    meta["verified"] = existing + [entry]
    stale = stale_after_for(str(meta.get("type", "")))
    if stale:
        meta["stale_after"] = stale
    if meta.get("status") == "draft":
        meta["status"] = "stable"
    write(path, meta, body)
    log_append(path.parent if path.parent.name != "docs" or True else path.parent,
               f"**Verification** {meta.get('title', path.stem)} by {by}." + (f" {note}" if note else ""))
    return {"path": path.relative_to(root).as_posix(), "verified_by": by, "tier": trust_tier(meta), "stale_after": stale}


def set_status(root: Path, concept_id: str, status: str, reason: str = "") -> dict:
    if status not in STATUSES:
        raise KitError(f"status must be one of {', '.join(STATUSES)}")
    path = _find(root, concept_id)
    meta, body = read(path)
    if meta is None:
        raise KitError(f"{concept_id} has no frontmatter")
    meta["status"] = status
    if status == "deprecated":
        meta.pop("stale_after", None)
    write(path, meta, body)
    word = {"deprecated": "Deprecation", "stable": "Promotion", "draft": "Update"}[status]
    log_append(path.parent, f"**{word}** {meta.get('title', path.stem)}." + (f" {reason}" if reason else ""))
    return {"path": path.relative_to(root).as_posix(), "status": status}


def promote_drafts(root: Path, days: int = 7) -> list[str]:
    """D71: drafts older than a week become stable unless deprecated."""
    promoted = []
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
    docs = root / "docs"
    if not docs.exists():
        return promoted
    for path in concept_files(docs):
        meta, _ = read(path)
        if not meta or meta.get("status") != "draft":
            continue
        gen = (meta.get("generated") or {}).get("at")
        try:
            when = dt.datetime.fromisoformat(str(gen).replace("Z", "+00:00")) if gen else None
        except ValueError:
            when = None
        if when and when.tzinfo is None:
            when = when.replace(tzinfo=dt.timezone.utc)
        if when and when <= cutoff:
            set_status(root, path.relative_to(root).as_posix(), "stable", "A week old with no objection.")
            promoted.append(path.relative_to(root).as_posix())
    return promoted


# ---------------------------------------------------------------- staleness across the hub

def stale_concepts(root: Path) -> list[dict]:
    """Every concept past stale_after: docs/, packet READMEs, GLOSSARY.md."""
    found = []
    candidates: list[Path] = []
    docs = root / "docs"
    if docs.exists():
        candidates += concept_files(docs)
    for folder in ("explorations", "goals"):
        base = root / folder
        if base.exists():
            candidates += sorted(base.glob("*/README.md"))
    if (root / "GLOSSARY.md").exists():
        candidates.append(root / "GLOSSARY.md")
    for path in candidates:
        meta, _ = read(path)
        if not meta or meta.get("status") == "deprecated":
            continue
        if is_stale(meta):
            found.append({"path": path.relative_to(root).as_posix(), "type": meta.get("type"),
                          "title": meta.get("title") or path.stem, "stale_after": meta.get("stale_after"),
                          "tier": trust_tier(meta), "sources": len(meta.get("sources") or [])})
    return found


def duplicate_drafts(root: Path) -> list[list[str]]:
    """Draft concepts whose titles or slugs look alike, for the gardener to merge."""
    docs = root / "docs"
    if not docs.exists():
        return []
    drafts = []
    for path in concept_files(docs):
        meta, _ = read(path)
        if meta and meta.get("status") == "draft":
            words = set(re.findall(r"[a-z0-9]+", str(meta.get("title") or path.stem).lower())) - {"the", "a", "an", "of", "to", "and", "for", "in", "on"}
            drafts.append((path.relative_to(root).as_posix(), words, str(meta.get("type"))))
    groups = []
    seen: set[str] = set()
    for i, (p1, w1, t1) in enumerate(drafts):
        if p1 in seen:
            continue
        group = [p1]
        for p2, w2, t2 in drafts[i + 1:]:
            if p2 in seen or t1 != t2 or not w1 or not w2:
                continue
            overlap = len(w1 & w2) / min(len(w1), len(w2))
            if overlap >= 0.6:
                group.append(p2)
                seen.add(p2)
        if len(group) > 1:
            seen.update(group)
            groups.append(group)
    return groups


# ---------------------------------------------------------------- reserved files

def log_append(folder: Path, text: str) -> None:
    path = folder / "log.md"
    today = dt.date.today().isoformat()
    existing = path.read_text(encoding="utf-8") if path.exists() else "# Log\n\nNewest first. The kit writes this; nobody edits it.\n"
    head, _, rest = existing.partition("\n## ")
    sections = ("## " + rest) if rest else ""
    if sections.startswith(f"## {today}\n"):
        first, _, remainder = sections.partition("\n\n")
        sections = f"{first}\n- {text}\n\n{remainder}" if remainder else f"{first}\n- {text}\n"
    else:
        sections = f"## {today}\n\n- {text}\n\n{sections}" if sections else f"## {today}\n\n- {text}\n"
    path.write_text(head.rstrip("\n") + "\n\n" + sections.rstrip("\n") + "\n", encoding="utf-8")


def write_indexes(root: Path) -> dict:
    docs = root / "docs"
    if not docs.exists():
        return {"folders": 0}
    folders = {docs}
    for p in concept_files(docs):
        folders.add(p.parent)
    for folder in sorted(folders):
        lines = []
        if folder == docs:
            lines += ["---", 'okf_version: "0.2"', "---", "", "# Docs", "",
                      "Notes, how-tos and facts worth keeping, one per page. The tier in brackets says who last",
                      "checked a page: a person, the kit, or nobody yet.", ""]
        else:
            lines += [f"# {folder.name.replace('-', ' ').capitalize()}", ""]
        entries = sorted(p for p in folder.glob("*.md") if p.name not in RESERVED)
        subfolders = sorted(p for p in folder.iterdir() if p.is_dir() and any(concept_files(p)))
        if entries:
            lines += ["## Pages", ""]
            for p in entries:
                meta, _ = read(p)
                meta = meta or {}
                title = meta.get("title") or p.stem
                desc = meta.get("description") or ""
                flags = [trust_tier(meta)]
                if meta.get("status") and meta.get("status") != "stable":
                    flags.append(str(meta["status"]))
                if is_stale(meta):
                    flags.append("stale")
                lines.append(f"* [{title}]({p.name}) - {desc} [{', '.join(flags)}]")
            lines.append("")
        if subfolders:
            lines += ["## Folders", ""]
            lines += [f"* [{d.name}]({d.name}/index.md) - {len(concept_files(d))} page(s)" for d in subfolders]
            lines.append("")
        (folder / "index.md").write_text("\n".join(lines), encoding="utf-8")
    return {"folders": len(folders)}


# ---------------------------------------------------------------- validation (OKF v0.2 §11)

def validate(bundle: Path) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    error_files: set[str] = set()
    concepts = 0

    def fail(rel: str, message: str) -> None:
        errors.append(f"{message.split(' ', 1)[0]} {rel}: {message.split(' ', 1)[1]}")
        error_files.add(rel)

    for path in sorted(bundle.rglob("*.md")):
        if ".git" in path.parts:
            continue
        rel = path.relative_to(bundle).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace")
        if path.name == "index.md":
            meta, _ = split_frontmatter(text)
            if meta is not None and (rel != "index.md" or set(meta) != {"okf_version"}):
                fail(rel, "E3 index.md may carry only okf_version at the bundle root")
            continue
        if path.name == "log.md":
            if text.strip() and not re.search(r"^## \d{4}-\d{2}-\d{2}", text, re.M):
                warnings.append(f"W5 {rel}: log.md has no date headings")
            continue
        concepts += 1
        try:
            meta, _ = split_frontmatter(text)
        except KitError as exc:
            fail(rel, f"E1 frontmatter does not parse ({exc})")
            continue
        if meta is None:
            fail(rel, "E1 no YAML frontmatter")
            continue
        for problem in strict_yaml_problems(text):
            fail(rel, f"E7 {problem}")
        if not str(meta.get("type") or "").strip():
            fail(rel, "E2 missing or empty type")
            continue
        if meta.get("status") not in (None, *STATUSES):
            fail(rel, "E5 status must be draft, stable or deprecated")
        if not meta.get("description"):
            warnings.append(f"W1 {rel}: no description")
        gen = meta.get("generated")
        if gen is not None and (not isinstance(gen, dict) or not gen.get("by")):
            fail(rel, "E6 generated needs a by")
    return {"bundle": str(bundle), "ok": not errors, "concepts": concepts, "errors": errors,
            "files": sorted(error_files), "warnings": warnings}


# A plain (unquoted) value that a standard YAML reader would reject or cut
# short: `title: Fees: 10%` (a mapping inside a value) or `title: a #b` (a
# comment). The kit's reader forgives both; okflint, Obsidian and every other
# tool don't. This is a heuristic for what the kit and most agents write, not
# a YAML parser: it only looks at `key: value` lines (optionally a `- ` list
# item) whose key is letters, digits, `_`, `.` or `-`, and it skips values
# that start with a quote, a flow collection or a block indicator. It can
# miss a problem (other key characters, a plain scalar in a block list); it
# never flags valid YAML. `kit docs lint` (okflint, a real YAML parser) is the
# complete check.
_PLAIN_VALUE = re.compile(r"^(?P<lead>\s*(?:- )?[A-Za-z0-9_.-]+:[ \t]+)(?![\"'\[{|>&*!])(?P<value>.+?)(?P<trail>\s*)$")


def _frontmatter_span(text: str) -> tuple[int, int] | None:
    """Start and end offsets of the frontmatter lines, between the fences."""
    if not text.startswith(("---\n", "---\r\n")):
        return None
    end = re.search(r"\n---[ \t]*\r?(\n|$)", text[3:])
    if not end:
        return None
    start = 5 if text.startswith("---\r\n") else 4
    return start, 3 + end.start() + 1


def _needs_quotes(value: str) -> bool:
    return ": " in value or value.endswith(":") or " #" in value


def strict_yaml_problems(text: str) -> list[str]:
    span = _frontmatter_span(text)
    if span is None:
        return []
    problems = []
    for n, line in enumerate(text[span[0]:span[1]].splitlines(), start=2):
        m = _PLAIN_VALUE.match(line)
        if m and _needs_quotes(m.group("value")):
            problems.append(f"line {n} needs quotes around its value ({line.strip()[:60]!r})")
    return problems


def quote_problem_values(text: str) -> str:
    """Quote, in place, each value `strict_yaml_problems` flags, and change
    nothing else: comments, key order, spacing and the body stay as they were.
    Single quotes when the value has no apostrophe (YAML and the kit then read
    backslashes literally); otherwise double quotes, escaping backslashes and
    double quotes, which both readers undo the same way."""
    span = _frontmatter_span(text)
    if span is None:
        return text
    lines = text[span[0]:span[1]].splitlines(keepends=True)
    for i, line in enumerate(lines):
        body = line.rstrip("\r\n")
        m = _PLAIN_VALUE.match(body)
        if not m or not _needs_quotes(m.group("value")):
            continue
        value = m.group("value")
        if "'" not in value:
            quoted = f"'{value}'"
        else:
            quoted = '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
        lines[i] = m.group("lead") + quoted + m.group("trail") + line[len(body):]
    return text[:span[0]] + "".join(lines) + text[span[1]:]


# ---------------------------------------------------------------- okflint (D82)

# Pinned, with its dependencies pinned too and resolution fenced to the date
# they were checked, so a later upload can't change what runs. PyPI versions
# are immutable; `uv tool run` has no hash-checking mode. Bump all three on
# purpose, with the CI run as the check.
OKFLINT = "okflint==0.5.1"
OKFLINT_WITH = ("beartype==0.23.1", "pyyaml==6.0.3")
OKFLINT_EXCLUDE_NEWER = "2026-11-09T00:00:00Z"
MANIFEST = KIT_ROOT / "okf-base.yaml"


def lint(bundle: Path, timeout: float = 180) -> dict:
    """Run the pinned okflint over a bundle with the kit's manifest. Never
    installs anything globally: `uv tool run` caches the pinned version. When
    uv, Python 3.12 or the network is missing the result is `skipped`, not a
    failure, because `validate` still ran and the user must never be asked to
    install a linter."""
    bundle = bundle.resolve()
    if not bundle.is_dir():
        raise KitError(f"no docs folder at {bundle}")
    empty = {"bundle": str(bundle), "ok": None, "errors": [], "files": [], "warnings": []}
    if shutil.which("uv") is None:
        return {**empty, "skipped": "uv is not installed"}
    with_args = [arg for dep in OKFLINT_WITH for arg in ("--with", dep)]
    with tempfile.TemporaryDirectory(prefix="kit-okflint-") as tmp:
        manifest = Path(tmp) / "okf-base.yaml"
        root = bundle.as_posix().replace("'", "''")
        manifest.write_text(MANIFEST.read_text(encoding="utf-8").replace("{root}", root), encoding="utf-8")
        out = run(["uv", "tool", "run", "--quiet", "--exclude-newer", OKFLINT_EXCLUDE_NEWER, "--from", OKFLINT,
                   *with_args, "okflint", "validate", "--json", "--manifest", str(manifest)],
                  cwd=Path(tmp), timeout=timeout)
    try:
        diagnostics = json.loads(out.stdout or "null")
    except json.JSONDecodeError:
        diagnostics = None
    if not isinstance(diagnostics, list):
        reason = (out.stderr or out.stdout or "").strip().splitlines()[-1:] or [f"exit {out.returncode}"]
        return {**empty, "skipped": f"okflint did not run: {reason[0][:200]}"}
    failing = [d for d in diagnostics if d.get("severity") == "error"]
    errors = [f"{d.get('code')} {d.get('file')}: {d.get('message')}" for d in failing]
    warnings = [f"{d.get('code')} {d.get('file')}: {d.get('message')}" for d in diagnostics if d.get("severity") != "error"]
    files = sorted({str(d.get("file")) for d in failing if d.get("file")})
    return {"bundle": str(bundle), "ok": not errors, "linter": OKFLINT, "errors": errors, "files": files,
            "warnings": warnings}
