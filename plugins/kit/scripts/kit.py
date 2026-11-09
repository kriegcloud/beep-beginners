# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""The kit: the one command layer behind every skill, hook and caretaker run (D51).

  kit explore new <title> [--notes TEXT]      kit goal graduate <slug> <title> [--mission TEXT]
  kit explore set <slug> [--stage S] [--status S] [--next TEXT] [--trail TEXT]
  kit explore list                            kit goal set <slug> [--status S] [--trail TEXT]
  kit index
  kit project new <name> --stack python|ts [--goal SLUG] [--mode operator|mentor] [--summary TEXT] [--from DIR]
  kit project list
  kit land [--message TEXT]                   kit sync [--at start|end]
  kit pr open [--branch B] | list | watch <n> [--max-seconds N] | merge <n> | retry <n>
  kit chores list | due [--where W] | run [--where W] [--max-seconds N] [--all]
  kit needs-you add --title T (--brief TEXT | --brief-file F) | resolve <id> --outcome TEXT
  kit needs-you weekly --text TEXT | render | read
  kit explain --template brief|glossary-entry [--title T] | kit explain render --json FILE
  kit glossary add <term> --meaning TEXT
  kit profile draft <memories-file> | write --answers FILE
  kit security enable
  kit caretaker sweep [--dry-run] | pr <n> [--max-seconds N] | fetch --into DIR [--ref REF]
  kit caretaker install --workspace URL --environment ID --cron-utc EXPR [--route plugin|fetch|repo]
  kit hook guard | session-start | session-end       (called from hooks.json)

Standard library only. Output is JSON on stdout; errors are one plain sentence
on stderr with exit 1. People never run this; agents do.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent


# ---------------------------------------------------------------- bootstrap (no kitlib yet)

def fetch_kit(into: Path, ref: str) -> dict:
    """Download the plugin from raw.githubusercontent.com using its MANIFEST.
    Runs before kitlib exists, so it imports nothing from it."""
    base = f"https://raw.githubusercontent.com/kriegcloud/beep-beginners/{ref}/plugins/kit/"
    with urllib.request.urlopen(base + "MANIFEST", timeout=60) as resp:
        manifest = resp.read().decode("utf-8")
    files = [line.strip() for line in manifest.splitlines() if line.strip() and not line.startswith("#")]
    into.mkdir(parents=True, exist_ok=True)
    fetched = []
    for rel in files:
        dest = into / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(base + rel, timeout=60) as resp:
            dest.write_bytes(resp.read())
        fetched.append(rel)
    return {"into": str(into), "ref": ref, "files": len(fetched), "kit": str(into / "scripts" / "kit.py")}


# ---------------------------------------------------------------- argument parsing

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kit", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=None, help="workspace folder (default: the current folder)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("explore"); s = p.add_subparsers(dest="sub", required=True)
    q = s.add_parser("new"); q.add_argument("title"); q.add_argument("--notes")
    q = s.add_parser("set"); q.add_argument("slug"); q.add_argument("--stage"); q.add_argument("--status")
    q.add_argument("--next"); q.add_argument("--trail")
    s.add_parser("list")

    p = sub.add_parser("goal"); s = p.add_subparsers(dest="sub", required=True)
    q = s.add_parser("graduate"); q.add_argument("slug"); q.add_argument("title"); q.add_argument("--mission")
    q = s.add_parser("set"); q.add_argument("slug"); q.add_argument("--status"); q.add_argument("--trail")

    sub.add_parser("index")

    p = sub.add_parser("project"); s = p.add_subparsers(dest="sub", required=True)
    q = s.add_parser("new"); q.add_argument("name"); q.add_argument("--stack", required=True, choices=["python", "ts"])
    q.add_argument("--goal"); q.add_argument("--mode", default="operator", choices=["operator", "mentor"])
    q.add_argument("--summary", default=""); q.add_argument("--from", dest="source", type=Path)
    s.add_parser("list")

    p = sub.add_parser("land"); p.add_argument("--message"); p.add_argument("--allow-secrets", action="store_true", help=argparse.SUPPRESS)
    p = sub.add_parser("sync"); p.add_argument("--at", default="start", choices=["start", "end"])

    p = sub.add_parser("pr"); s = p.add_subparsers(dest="sub", required=True)
    q = s.add_parser("open"); q.add_argument("--branch"); q.add_argument("--title"); q.add_argument("--body")
    s.add_parser("list")
    q = s.add_parser("watch"); q.add_argument("number", type=int); q.add_argument("--max-seconds", type=int, default=1200)
    q = s.add_parser("merge"); q.add_argument("number", type=int)
    q = s.add_parser("retry"); q.add_argument("number", type=int)

    p = sub.add_parser("chores"); s = p.add_subparsers(dest="sub", required=True)
    s.add_parser("list")
    q = s.add_parser("due"); q.add_argument("--where", default="desktop", choices=["desktop", "cloud"])
    q = s.add_parser("run"); q.add_argument("--where", default="desktop", choices=["desktop", "cloud"])
    q.add_argument("--max-seconds", type=int, default=120); q.add_argument("--all", action="store_true")

    p = sub.add_parser("needs-you"); s = p.add_subparsers(dest="sub", required=True)
    q = s.add_parser("add"); q.add_argument("--title", required=True); q.add_argument("--brief"); q.add_argument("--brief-file", type=Path)
    q.add_argument("--source", default="caretaker"); q.add_argument("--kind", default="decision")
    q = s.add_parser("resolve"); q.add_argument("id"); q.add_argument("--outcome", required=True)
    q = s.add_parser("weekly"); q.add_argument("--text", required=True)
    s.add_parser("render"); s.add_parser("read")

    p = sub.add_parser("explain"); p.add_argument("--template", default="brief", choices=["brief", "glossary-entry"])
    p.add_argument("--title"); p.add_argument("--json", dest="json_file", type=Path, help="render a filled brief from JSON")

    p = sub.add_parser("glossary"); s = p.add_subparsers(dest="sub", required=True)
    q = s.add_parser("add"); q.add_argument("term"); q.add_argument("--meaning", required=True)

    p = sub.add_parser("profile"); s = p.add_subparsers(dest="sub", required=True)
    q = s.add_parser("draft"); q.add_argument("memories", type=Path)
    q = s.add_parser("write"); q.add_argument("--answers", type=Path, required=True)

    p = sub.add_parser("security"); s = p.add_subparsers(dest="sub", required=True)
    s.add_parser("enable")

    p = sub.add_parser("caretaker"); s = p.add_subparsers(dest="sub", required=True)
    q = s.add_parser("sweep"); q.add_argument("--dry-run", action="store_true")
    q = s.add_parser("pr"); q.add_argument("number", type=int); q.add_argument("--max-seconds", type=int, default=1200)
    q = s.add_parser("fetch"); q.add_argument("--into", type=Path, required=True); q.add_argument("--ref", default="main")
    q = s.add_parser("install"); q.add_argument("--workspace", required=True); q.add_argument("--environment", required=True)
    q.add_argument("--cron-utc", required=True); q.add_argument("--route", default="fetch", choices=["plugin", "fetch", "repo"])
    q.add_argument("--ref", default="main")

    p = sub.add_parser("hook"); p.add_argument("event", choices=["guard", "session-start", "session-end"])
    return parser


# ---------------------------------------------------------------- dispatch

def dispatch(args: argparse.Namespace):
    if args.cmd == "caretaker" and args.sub == "fetch":
        return fetch_kit(args.into, args.ref)

    sys.path.insert(0, str(HERE))
    from kitlib import caretaker, chores, explain, github, landing, needs_you, packets, profile, project  # noqa: E402
    from kitlib.common import KitError, require_root  # noqa: E402

    start = (args.root or Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path.cwd())).resolve()

    if args.cmd == "hook":
        from kitlib import hooks  # noqa: E402
        return hooks.run(args.event, start)
    if args.cmd == "explain":
        if args.json_file:
            return {"brief": explain.render_brief(json.loads(args.json_file.read_text(encoding="utf-8")))}
        if args.template == "glossary-entry":
            return {"template": explain.GLOSSARY_ENTRY.format(term="<term>", meaning="<one plain sentence>")}
        return {"template": explain.brief_template(args.title or "<the decision in a few words>")}
    if args.cmd == "profile" and args.sub == "draft":
        return profile.draft(args.memories.read_text(encoding="utf-8", errors="replace"))
    if args.cmd == "caretaker" and args.sub == "install":
        return caretaker.install_bodies(args.workspace, args.environment, args.cron_utc, args.ref, args.route)
    if args.cmd == "profile":  # runs before the workspace is a git repository
        return profile.write(start, json.loads(args.answers.read_text(encoding="utf-8")))

    root = require_root(start)
    if args.cmd == "explore":
        if args.sub == "new":
            return packets.explore_new(root, args.title, args.notes)
        if args.sub == "set":
            return packets.explore_set(root, args.slug, args.stage, args.status, args.next, args.trail)
        return packets.list_all(root)
    if args.cmd == "goal":
        if args.sub == "graduate":
            return packets.goal_graduate(root, args.slug, args.title, args.mission)
        return packets.goal_set(root, args.slug, args.status, args.trail)
    if args.cmd == "index":
        return packets.write_index(root)
    if args.cmd == "project":
        if args.sub == "new":
            return project.new(root, args.name, args.stack, args.goal, args.mode, args.summary, args.source)
        return {"projects": project.list_projects(root)}
    if args.cmd == "land":
        return landing.land(root, args.message, allow_secrets=args.allow_secrets)
    if args.cmd == "sync":
        return landing.sync(root, args.at, open_pr=_open_pr_for_branch)
    if args.cmd == "pr":
        slug = github.repo_slug(root)
        if args.sub == "open":
            branch = args.branch or landing.current_branch(root)
            return _open_pr_for_branch(root, branch, None, args.title, args.body) or {"opened": False}
        if args.sub == "list":
            return {"pulls": github.list_prs(slug)}
        if args.sub == "watch":
            return github.watch_pr(slug, args.number, max_seconds=args.max_seconds)
        if args.sub == "merge":
            return github.merge_pr(slug, args.number)
        return github.retry_failed_checks(slug, args.number)
    if args.cmd == "chores":
        if args.sub == "list":
            return {"chores": chores.load_chores()}
        if args.sub == "due":
            return {"due": chores.due(root, args.where)}
        return chores.run_due(root, args.where, args.max_seconds, limit=None if args.all else 1)
    if args.cmd == "needs-you":
        if args.sub == "add":
            brief = args.brief or (args.brief_file.read_text(encoding="utf-8") if args.brief_file else "")
            if not brief:
                raise KitError("an item needs a brief (--brief or --brief-file)")
            return needs_you.add(root, args.title, brief, args.source, args.kind)
        if args.sub == "resolve":
            return needs_you.resolve(root, args.id, args.outcome)
        if args.sub == "weekly":
            return needs_you.weekly(root, args.text)
        if args.sub == "render":
            return {"rendered": needs_you.render(root)}
        return needs_you.read_aloud(root)
    if args.cmd == "glossary":
        return explain.glossary_add(root, args.term, args.meaning)
    if args.cmd == "security":
        return github.enable_security(github.repo_slug(root))
    if args.cmd == "caretaker":
        if args.sub == "sweep":
            return caretaker.sweep(root, dry_run=args.dry_run)
        return caretaker.handle_pr(root, args.number, args.max_seconds)
    raise KitError(f"unknown command {args.cmd}")


def _open_pr_for_branch(root: Path, branch: str, project_name: str | None, title: str | None = None,
                        body: str | None = None) -> dict | None:
    from kitlib import github  # noqa: E402
    slug = github.repo_slug(root)
    if branch == "main":
        return None
    name = project_name or branch.split("/", 1)[-1]
    title = title or f"Update {name}"
    body = body or (f"Changes to `projects/{name}` from a workspace session. The caretaker merges this when every "
                    f"check is green; nobody needs to review it by hand.\n\nBranch `{branch}`.")
    return github.open_pr(slug, branch, title, body)


def main() -> int:
    args = build_parser().parse_args()
    try:
        result = dispatch(args)
    except Exception as exc:  # noqa: BLE001
        from_kit = exc.__class__.__name__ == "KitError"
        print(str(exc) if from_kit else f"{exc.__class__.__name__}: {exc}", file=sys.stderr)
        return 1
    if args.cmd == "hook":
        return int(result)
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
