---
name: okf
description: >
  How to write and maintain pages in docs/, which is an Open Knowledge Format
  (OKF v0.2) bundle (D60, D82). Use whenever you create, edit, enrich, split,
  cross-link or import pages under docs/, convert a Notion export, Obsidian
  vault or spreadsheet into docs/, fix a page that `kit docs validate` or
  `kit docs lint` flagged, or the user mentions OKF, the knowledge base, or
  "the docs". For saving what a session learned, use the `remember` skill.
---

# OKF in this workspace

`docs/` is an Open Knowledge Format bundle: one concept per markdown file,
YAML frontmatter with a `type`, and `index.md` and `log.md` reserved in every
folder. The format guidance is the upstream OKF skill, vendored unchanged at a
pinned commit in `upstream/` (Apache-2.0, see `upstream/LICENSE` and
`UPSTREAM.json`). This file says where the kit overrides it.

## Read upstream for the format

- `upstream/UPSTREAM-SKILL.md`: frontmatter fields, `sources` with per-claim
  footnotes, cross-links, enrichment, and the conversion recipes.
- `upstream/references/spec-v02.md`: the spec the kit targets. Where it and
  `spec-v01.md` disagree, v0.2 wins. Never write v0.1 forms: no `timestamp`
  key, no `# Citations` heading, no bare-date `generated.at`.
- `upstream/references/conversion.md` and `examples.md`: importing Notion,
  Obsidian or CSV material.

## Kit overrides (these win over upstream)

1. **New pages go through the kit.** `kit docs new` sets `generated`,
   `status: draft`, `stale_after` from the type's default (D61) and updates
   the log and indexes. Write the body yourself; don't hand-roll frontmatter
   for a new page.
2. **Never write `index.md` or `log.md` by hand**, and never run
   `okflint index --apply`. `kit index` writes the indexes with trust tiers;
   `kit land` and `kit docs new` append to the log.
3. **Validate with the kit, not with `validate.sh`.** The user is on Windows,
   and `validate.sh` is bash. `kit docs validate` is the fast check and needs
   nothing installed. `kit docs lint` runs okflint at a version the kit pins,
   through `uv`, with the kit's manifest. It parses YAML strictly and checks
   links and the v0.2 field shapes. Never ask the user to install okflint
   or anything else for this: if `uv` or the network is missing, lint reports
   `skipped` and that's fine.
4. **Quote any value that contains `: ` or ` #`.** The kit's own reader
   forgives `title: Fees: 10%`, but standard YAML readers reject it
   (`E7` in `kit docs validate`, `F001` in `kit docs lint`).
5. **Trust fields belong to the kit.** Record a check with
   `kit docs verify <id> --by human:<name>` (the user confirmed it) or
   `--by claude-code/<model>` (you rechecked it against its `sources`), and
   retire a page with `kit docs deprecate <id> --reason "..."`. Don't edit
   `verified`, `status` or `stale_after` by hand. `status` is the trust tier,
   never a project's lifecycle.
6. **No Knowledge Catalog.** Ignore the `kcmd` and Google Cloud sections;
   this workspace syncs through git and GitHub only.
7. **The never-list applies to every page**, imports included: no health,
   relationships, personal finances, other people by name, or secrets. Drop
   such material from an import and tell the user in one line that you did.
8. **One concept per file.** When lint reports `S202` (split candidate),
   split the page only if it really holds two facts; otherwise leave it.

## Maintenance loop

```
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/kit.py" docs validate      # structure, offline, instant
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/kit.py" docs lint          # okflint: strict YAML, links, v0.2 shapes
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/kit.py" docs stale         # pages past stale_after: recheck or deprecate
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/kit.py" docs duplicates    # drafts that say the same thing
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/kit.py" index              # rewrite every folder's index.md
```

Fix every error and save with `kit land --message "Docs: <one line>"`.
Warnings are yours to judge and never reach the user. The weekly
`okf-validate` chore runs `validate` and `lint` and tells the user one line
only when a page needs fixing.
