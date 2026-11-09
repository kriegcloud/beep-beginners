# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""The kit: the one command layer behind every skill, hook and caretaker run (D51).

  kit explore new <title> [--notes TEXT] | set <slug> [...] | list | confirm <slug> --by human:<name>
  kit goal graduate <slug> <title> [--mission TEXT] | set <slug> [--status S] [--trail TEXT]
  kit index
  kit project new <name> --stack python|ts [--goal SLUG] [--mode operator|mentor] [--summary TEXT] [--from DIR] | list
  kit land [--message TEXT]                   kit sync [--at start|end]
  kit pr open [--branch B] [--review FILE] | list | watch <n> | merge <n> | retry <n>
  kit pr review-status <n> --state success|failure --description TEXT
  kit review record --goal SLUG --project NAME --findings N --fixed N --waivers FILE|--no-waivers
  kit chores list | due [--where W] | run [--where W] [--max-seconds N] [--all]
  kit needs-you add --title T (--brief TEXT | --brief-file F) | resolve <id> --outcome TEXT | weekly --text T | render | read
  kit explain [--template brief|glossary-entry] [--title T] | --json FILE
  kit glossary add <term> --meaning TEXT
  kit docs new --type T --title T (--body TEXT | --body-file F) [--folder F] [--description D] [--source URL ...] [--by ACTOR] [--export]
  kit docs validate [PATH] | stale | verify <id> --by ACTOR | deprecate <id> [--reason R] | promote | duplicates
  kit retro open --goal SLUG --summary TEXT | add --goal SLUG --text T --kind chore|step|decision|lesson --due DATE
  kit retro done --goal SLUG <id> | list [--goal SLUG] | overdue | nag
  kit feedback add --what T --fix T [--file F] | list | send
  kit migrate [--dry-run]
  kit profile draft <memories-file> | write --answers FILE
  kit security enable
  kit caretaker idle [--garden] | sweep [--dry-run] | pr <n> [--max-seconds N] | garden [--dry-run]
  kit caretaker fix-used | record --sweep ID --pr ID --garden ID [--runner R] [--plan P] | pause
  kit caretaker fetch --into DIR [--ref REF]
  kit caretaker install --workspace URL --environment ID --cron-utc EXPR [--garden-cron-utc EXPR] [--route repo] [--runner cloud|actions] [--ref stable]
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
    for rel in files:
        dest = into / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(base + rel, timeout=60) as resp:
            dest.write_bytes(resp.read())
    return {"into": str(into), "ref": ref, "files": len(files), "kit": str(into / "scripts" / "kit.py")}


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
    q = s.add_parser("confirm"); q.add_argument("slug"); q.add_argument("--by", required=True)

    p = sub.add_parser("goal"); s = p.add_subparsers(dest="sub", required=True)
    q = s.add_parser("graduate"); q.add_argument("slug"); q.add_argument("title"); q.add_argument("--mission")
    q = s.add_parser("set"); q.add_argument("slug"); q.add_argument("--status"); q.add_argument("--trail")
    q = s.add_parser("confirm"); q.add_argument("slug"); q.add_argument("--by", required=True)

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
    q.add_argument("--review", type=Path, help="review record from `kit review record`")
    s.add_parser("list")
    q = s.add_parser("watch"); q.add_argument("number", type=int); q.add_argument("--max-seconds", type=int, default=1200)
    q = s.add_parser("merge"); q.add_argument("number", type=int)
    q = s.add_parser("retry"); q.add_argument("number", type=int)
    q = s.add_parser("review-status"); q.add_argument("number", type=int)
    q.add_argument("--state", required=True, choices=["success", "failure", "pending", "error"]); q.add_argument("--description", required=True)

    p = sub.add_parser("review"); s = p.add_subparsers(dest="sub", required=True)
    q = s.add_parser("record"); q.add_argument("--goal", required=True); q.add_argument("--project", required=True)
    q.add_argument("--findings", type=int, default=0); q.add_argument("--fixed", type=int, default=0)
    q.add_argument("--waivers", type=Path); q.add_argument("--no-waivers", action="store_true")

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
    p.add_argument("--title"); p.add_argument("--json", dest="json_file", type=Path)

    p = sub.add_parser("glossary"); s = p.add_subparsers(dest="sub", required=True)
    q = s.add_parser("add"); q.add_argument("term"); q.add_argument("--meaning", required=True)

    p = sub.add_parser("docs"); s = p.add_subparsers(dest="sub", required=True)
    q = s.add_parser("new"); q.add_argument("--type", required=True); q.add_argument("--title", required=True)
    q.add_argument("--body"); q.add_argument("--body-file", type=Path); q.add_argument("--folder", default="")
    q.add_argument("--description", default=""); q.add_argument("--source", action="append", default=[])
    q.add_argument("--by", default="process:kit"); q.add_argument("--status", default="draft", choices=["draft", "stable"])
    q.add_argument("--export", action="store_true", help="a session-end memory export (D71 type allowlist applies)")
    q = s.add_parser("validate"); q.add_argument("path", nargs="?", type=Path)
    s.add_parser("stale")
    q = s.add_parser("verify"); q.add_argument("id"); q.add_argument("--by", required=True); q.add_argument("--note", default="")
    q = s.add_parser("deprecate"); q.add_argument("id"); q.add_argument("--reason", default="")
    s.add_parser("promote"); s.add_parser("duplicates")

    p = sub.add_parser("retro"); s = p.add_subparsers(dest="sub", required=True)
    q = s.add_parser("open"); q.add_argument("--goal", required=True); q.add_argument("--summary", required=True)
    q = s.add_parser("add"); q.add_argument("--goal", required=True); q.add_argument("--text", required=True)
    q.add_argument("--kind", required=True, choices=["chore", "step", "decision", "lesson"]); q.add_argument("--due", required=True)
    q = s.add_parser("done"); q.add_argument("--goal", required=True); q.add_argument("id"); q.add_argument("--note", default="")
    q = s.add_parser("list"); q.add_argument("--goal")
    s.add_parser("overdue"); s.add_parser("nag")

    p = sub.add_parser("feedback"); s = p.add_subparsers(dest="sub", required=True)
    q = s.add_parser("add"); q.add_argument("--what", required=True); q.add_argument("--fix", required=True); q.add_argument("--file", default="")
    s.add_parser("list"); s.add_parser("send")

    p = sub.add_parser("migrate"); p.add_argument("--dry-run", action="store_true")

    p = sub.add_parser("profile"); s = p.add_subparsers(dest="sub", required=True)
    q = s.add_parser("draft"); q.add_argument("memories", type=Path)
    q = s.add_parser("write"); q.add_argument("--answers", type=Path, required=True)

    p = sub.add_parser("security"); s = p.add_subparsers(dest="sub", required=True)
    s.add_parser("enable")

    p = sub.add_parser("caretaker"); s = p.add_subparsers(dest="sub", required=True)
    q = s.add_parser("idle"); q.add_argument("--garden", action="store_true")
    q = s.add_parser("sweep"); q.add_argument("--dry-run", action="store_true")
    q = s.add_parser("pr"); q.add_argument("number", type=int); q.add_argument("--max-seconds", type=int, default=1200)
    q = s.add_parser("garden"); q.add_argument("--dry-run", action="store_true")
    s.add_parser("fix-used"); s.add_parser("pause")
    q = s.add_parser("record"); q.add_argument("--sweep", default=""); q.add_argument("--pr", default=""); q.add_argument("--garden", default="")
    q.add_argument("--runner", default="cloud"); q.add_argument("--plan")
    q = s.add_parser("fetch"); q.add_argument("--into", type=Path, required=True); q.add_argument("--ref", default="main")
    q = s.add_parser("install"); q.add_argument("--workspace", required=True); q.add_argument("--environment", default="")
    q.add_argument("--cron-utc", required=True); q.add_argument("--garden-cron-utc")
    q.add_argument("--route", default="repo", choices=["plugin", "fetch", "repo"],
                   help="repo is the only route that runs in the cloud (D45 as amended); plugin and fetch stay for the record")
    q.add_argument("--runner", default="cloud", choices=["cloud", "actions"]); q.add_argument("--ref", default="stable")

    p = sub.add_parser("hook"); p.add_argument("event", choices=["guard", "session-start", "session-end"])
    return parser


# ---------------------------------------------------------------- dispatch

def dispatch(args: argparse.Namespace):
    if args.cmd == "caretaker" and args.sub == "fetch":
        return fetch_kit(args.into, args.ref)

    sys.path.insert(0, str(HERE))
    from kitlib import caretaker, chores, explain, feedback, github, landing, migrate, needs_you, okf, packets, profile, project, retro  # noqa: E402
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
    if args.cmd == "profile":  # runs before the workspace is a git repository
        return profile.write(start, json.loads(args.answers.read_text(encoding="utf-8")))
    if args.cmd == "caretaker" and args.sub == "install":
        if args.runner == "cloud" and not args.environment:
            raise KitError("--environment is required for the cloud runner")
        return caretaker.install_bodies(args.workspace, args.environment, args.cron_utc, args.ref, args.route,
                                        args.garden_cron_utc, args.runner)
    if args.cmd == "docs" and args.sub == "validate" and args.path:
        return okf.validate(args.path.resolve())

    root = require_root(start)
    if args.cmd == "explore":
        if args.sub == "new":
            return packets.explore_new(root, args.title, args.notes)
        if args.sub == "set":
            return packets.explore_set(root, args.slug, args.stage, args.status, args.next, args.trail)
        if args.sub == "confirm":
            return packets.confirm(root / "explorations" / args.slug, args.by)
        return packets.list_all(root)
    if args.cmd == "goal":
        if args.sub == "graduate":
            return packets.goal_graduate(root, args.slug, args.title, args.mission)
        if args.sub == "confirm":
            return packets.confirm(root / "goals" / args.slug, args.by)
        return packets.goal_set(root, args.slug, args.status, args.trail)
    if args.cmd == "index":
        result = packets.write_index(root)
        result.update(okf.write_indexes(root))
        return result
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
            review = json.loads(args.review.read_text(encoding="utf-8")) if args.review else _latest_review(root, branch)
            return _open_pr_for_branch(root, branch, None, args.title, args.body, review) or {"opened": False}
        if args.sub == "list":
            return {"pulls": github.list_prs(slug)}
        if args.sub == "watch":
            return github.watch_pr(slug, args.number, max_seconds=args.max_seconds)
        if args.sub == "merge":
            return github.merge_pr(slug, args.number)
        if args.sub == "review-status":
            pr = github.summarize_pr(github.get_pr(slug, args.number))
            return github.post_review_status(slug, pr["sha"], args.state, args.description)
        return github.retry_failed_checks(slug, args.number)
    if args.cmd == "review":
        return _review_record(root, args)
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
    if args.cmd == "docs":
        if args.sub == "new":
            body = args.body or (args.body_file.read_text(encoding="utf-8") if args.body_file else "")
            if not body:
                raise KitError("a page needs a body (--body or --body-file)")
            sources = [{"id": f"s{i + 1}", "resource": url} for i, url in enumerate(args.source)]
            return okf.concept_new(root, args.folder, args.title, args.type, body, args.description, sources,
                                   args.by, args.status, export=args.export)
        if args.sub == "validate":
            return okf.validate(root / "docs")
        if args.sub == "stale":
            return {"stale": okf.stale_concepts(root)}
        if args.sub == "verify":
            return okf.verify(root, args.id, args.by, args.note)
        if args.sub == "deprecate":
            return okf.set_status(root, args.id, "deprecated", args.reason)
        if args.sub == "promote":
            return {"promoted": okf.promote_drafts(root)}
        return {"duplicates": okf.duplicate_drafts(root)}
    if args.cmd == "retro":
        if args.sub == "open":
            return retro.open_retro(root, args.goal, args.summary)
        if args.sub == "add":
            return retro.add(root, args.goal, args.text, args.kind, args.due)
        if args.sub == "done":
            return retro.done(root, args.goal, args.id, args.note)
        if args.sub == "list":
            return {"items": retro.list_items(root, args.goal)}
        if args.sub == "overdue":
            return {"overdue": retro.overdue(root)}
        return {"nagged": retro.nag(root)}
    if args.cmd == "feedback":
        if args.sub == "add":
            return feedback.add(root, args.what, args.fix, args.file)
        if args.sub == "list":
            return feedback.load(root)
        return feedback.send(root)
    if args.cmd == "migrate":
        return migrate.run(root, dry_run=args.dry_run)
    if args.cmd == "security":
        return github.enable_security(github.repo_slug(root))
    if args.cmd == "caretaker":
        if args.sub == "idle":
            return caretaker.idle(root, garden=args.garden)
        if args.sub == "sweep":
            return caretaker.sweep(root, dry_run=args.dry_run)
        if args.sub == "pr":
            return caretaker.handle_pr(root, args.number, args.max_seconds)
        if args.sub == "garden":
            return caretaker.garden(root, dry_run=args.dry_run)
        if args.sub == "fix-used":
            return caretaker.fix_used(root)
        if args.sub == "record":
            return caretaker.record_routines(root, {"sweep": args.sweep, "pr_opened": args.pr, "garden": args.garden},
                                             args.runner, args.plan)
        return caretaker.pause_info(root)
    raise KitError(f"unknown command {args.cmd}")


def _review_record(root: Path, args: argparse.Namespace) -> dict:
    """D70: the desktop agent reviewed the project change; write the record into
    the goal packet and return what `kit pr open --review` posts."""
    from kitlib.common import KitError, today  # noqa: E402
    folder = root / "goals" / args.goal / "reviews"
    if not (root / "goals" / args.goal).exists():
        raise KitError(f"no goal at goals/{args.goal}")
    folder.mkdir(parents=True, exist_ok=True)
    waivers = args.waivers.read_text(encoding="utf-8").strip() if args.waivers else ""
    if not waivers and not args.no_waivers:
        raise KitError("give --waivers <file> (the findings left as they are, with a reason each) or --no-waivers")
    waived = len([ln for ln in waivers.splitlines() if ln.strip().startswith("-")]) if waivers else 0
    path = folder / f"{today()}-{args.project}.md"
    n = 2
    while path.exists():
        path = folder / f"{today()}-{args.project}-{n}.md"
        n += 1
    text = (f"---\ntype: review\ntitle: Review of {args.project} on {today()}\n"
            f"description: \"Code review before the change landed: {args.findings} finding(s), {args.fixed} fixed, {waived} waived.\"\n"
            f"status: stable\n---\n# Review of {args.project}, {today()}\n\n{args.findings} finding(s), {args.fixed} fixed, {waived} left as they are.\n\n"
            f"## Left as they are, and why\n\n{waivers or 'Nothing.'}\n")
    path.write_text(text, encoding="utf-8")
    from kitlib import landing  # noqa: E402
    # The verdict covers exactly this state of the project folder. A later push
    # changes the tree, and the stored record stops matching, so it is reviewed again.
    tree = landing.working_tree_of_prefix(root, f"projects/{args.project}")
    record = {"goal": args.goal, "project": args.project, "findings": args.findings, "fixed": args.fixed,
              "waived": waived, "record": path.relative_to(root).as_posix(), "date": today(), "tree": tree}
    (root / ".kit").mkdir(exist_ok=True)
    reviews = root / ".kit" / "reviews.json"
    data = json.loads(reviews.read_text(encoding="utf-8")) if reviews.exists() else {}
    data[landing.branch_for(root, args.project)] = record
    reviews.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return record


def _latest_review(root: Path, branch: str) -> dict | None:
    """The stored review for a branch, only while it still matches the branch
    tip's project tree (D70: a new push needs a new review)."""
    from kitlib import landing  # noqa: E402
    reviews = root / ".kit" / "reviews.json"
    if not reviews.exists():
        return None
    record = json.loads(reviews.read_text(encoding="utf-8")).get(branch)
    if not record:
        return None
    current = landing.tree_of_prefix(root, branch, f"projects/{record['project']}")
    if record.get("tree") and current and record["tree"] != current:
        return None
    return record


def _open_pr_for_branch(root: Path, branch: str, project_name: str | None, title: str | None = None,
                        body: str | None = None, review: dict | None = None) -> dict | None:
    from kitlib import github  # noqa: E402
    slug = github.repo_slug(root)
    if branch == "main":
        return None
    name = project_name or branch.split("/", 1)[-1]
    title = title or f"Update {name}"
    body = body or (f"Changes to `projects/{name}` from a workspace session. The caretaker merges this when every "
                    f"check is green and the kit/review verdict is posted; nobody needs to review it by hand.\n\nBranch `{branch}`.")
    if review is None:
        review = _latest_review(root, branch)
    return github.open_pr(slug, branch, title, body, review=review)


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
