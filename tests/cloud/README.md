# Cloud proof

The caretaker (D44 to D47) runs as Claude Code cloud scheduled tasks. This
proof shows one doing its job against a test workspace, and settles which way
the kit reaches the sandbox (D45). Nothing here touches a real user's
accounts: the workspace repo belongs to the test GitHub account, and the
tasks live on the operator's claude.ai account under the name
`beep-beginners-proof-*`, created one at a time with the operator's yes, and
deleted afterwards.

## Before

1. A test workspace repo exists (the VM proof makes it), with the kit's
   `security.yml` and at least one `projects/` folder.
2. The operator's claude.ai GitHub connection can reach that repo: the test
   account adds `kriegcloud` as a collaborator (approved 2026-11-08), and the
   Claude GitHub App is installed on the repo (the VM proof's github-app step).
3. The v3 kit is reachable from GitHub on a branch (`v3`), since every route
   below fetches it from there. `kit caretaker install --ref v3`.

## Facts learned on 2026-11-09 before the first cloud run

- The operator's Claude account was at its weekly limit (reset Nov 11, 10pm
  America/New_York), so routines created on it would be rejected until then:
  D66 observed before the caretaker even existed. The cloud proof waits for
  the reset.
- Adding the operator's GitHub user as a collaborator on the test repo is a
  documented manual proof step, like the Hello PIN and the Balanced preset in
  D41: the proof session's permission classifier refused it, Benjamin ran
  `gh api -X PUT repos/benjamintoppold-ai/workspace/collaborators/kriegcloud -f permission=push`
  himself in the VM's PowerShell as the test account on 2026-11-09, and the
  invitation was accepted as kriegcloud from the workstation. The kit never
  automates this: a real friend's caretaker runs on their own account against
  their own repository, so no second GitHub identity is involved.
- The test account's `gh` token is readable only in the VM's desktop logon
  session (Credential Manager); over the harness SSH session every `gh` call
  gets 401. Run proof scripts through `run.sh vmi`.
- Dependabot closed its first PR on the test repo as superseded when the kit's
  CI fix pinned the same commit, so the Dependabot proof uses an older ruff
  pin in `projects/sales-import`; the daily run proposes the bump, or the
  operator clicks "Check for updates" on the repo's Dependabot page.
- `kit pr merge` was already proven from the desktop: refused a red Dependabot
  PR, merged the green reviewed PR #2 (squash `0f3b81a`), refused PR #3 for a
  missing `kit/review` verdict. The cloud runs reuse that gate.

- Creating the first proof routine with Benjamin's yes was refused by the
  routines API: `403 repo_access_denied, "You don't have access to a repository
  this scheduled task uses."` Collaborator access on GitHub is not what the
  routines service checks; it checks the claude.ai account's GitHub
  connection. With the GitHub App connection that means the Claude GitHub App
  must be installed on the repository itself (by the repository's owner, the
  test account, in the VM's browser), which the webhook trigger needs anyway;
  with a `/web-setup` connection it means the connected `gh` token can reach
  the repository. For a real friend both are their own account, so onboarding's
  caretaker-setup step installs the App on the workspace first (D68).

## Routes to try, in order (D45)

| Route | How the kit gets in | What it costs |
| --- | --- | --- |
| `plugin` | routine `extra_marketplaces` + `enabled_plugins` | undocumented; may be ignored |
| `fetch` | `kit caretaker fetch` over raw.githubusercontent.com (default allowlist) | a committed `MANIFEST`; single-repo task keeps the workspace's deny rules |
| `repo` | the kit as the task's second repository | multi-repo task: no repo hooks or permission rules in the run |

For each: create the sweep routine with that route (`kit caretaker install
--route <route>`), `Run now`, read the run log (`RemoteTrigger get_run_log`),
and record whether `kit caretaker sweep` ran. First route that works wins;
the DECISIONS entry names it and quotes the evidence line.

## The runs to record

1. **Sweep merges a green PR.** From the VM (or any session on the test
   repo), land a `projects/` change so a `goal/*` PR exists with green
   checks. Run the sweep. Expect: `merged` lists it; the merge commit on
   `main` is by the operator's GitHub identity; `NEEDS-YOU.md` unchanged or
   updated with the weekly note on a Monday.
2. **Sweep refuses a red PR.** Open a PR on a `goal/*` branch whose test
   fails on purpose (a failing assertion). Run the sweep. Expect:
   `needs_fix` lists it with `kit_made: true`; the run makes one fix attempt
   or, if the fix isn't a lint/test fix, writes a NEEDS-YOU item. The PR is
   not merged while red.
3. **PR-opened trigger.** Open a new green PR. Expect a new run within the
   hour whose log shows `kit caretaker pr <n>` and a merge.
4. **Dependabot within a day.** The test project pins one dependency a
   version behind with `interval: daily`; the operator clicks "Check for
   updates" on the repo's Dependabot page. Expect the PR-opened run (or the
   next sweep) to merge it.

Record in `tests/cloud/evidence/<date>.md`: routine ids, run session ids,
the PR numbers, the merge commit shas, and which route won. No tokens, no
emails. The routines are deleted at claude.ai/code/routines when done (the
API can't delete them).
