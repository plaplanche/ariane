# Product brief: Add ariane verify to check and review a branch finished by hand (C10, C23)

- Source: issue #35 (https://github.com/plaplanche/ariane/issues/35)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

A hand takeover (after a second `no-go`, or a ticket Ariane cannot run, such as a workflow file pushed from the owner's machine) must get the same verification as Ariane's own tickets before its pull request: clean replay of the checks, one review, the review record (ADR 0016, ADR 0020, spec C10 and C23).

## Current state

`src/ariane/cli.py:36` `_parser` has `start` and `status`; the clean replay and the review exist in the ticket flow.

## Decided spec

- `ariane verify <branch> [--issue N]` runs on a branch that exists locally: a clean working tree at the branch's head (after the setup command), every check, then one review (the issue's text is given to the reviewer when `--issue` is passed, otherwise the branch's commit messages).
- It commits `work/verify/<branch-name>/review.md` and `checks.md` (redacted) to that branch, on top of its head, with Ariane's own git settings, and never pushes.
- Output: one line with the checks' summary, the verdict and the next action ("push the branch and open the pull request" on `go` with green blocking checks, otherwise "fix the findings, then run verify again"); exit code 0 only in the first case.
- It refuses a branch that is checked out in a working tree with uncommitted changes, naming them.

## Release note

Added: `ariane verify <branch>` checks and reviews a branch finished by hand.

## Acceptance criteria

- Tests named `test_c23_verify_*` show: a green branch with a `go` review gets the records committed and exit 0; a failing check or a `no-go` gives exit 1 and the next action; nothing is pushed; a dirty branch is refused.
- All checks in CLAUDE.md pass.

## Acceptance checklist

- [ ] `uv run pytest -k c23_verify` runs at least 4 tests and they pass.
- [ ] CLAUDE.md's "Developing Ariane with Ariane" says hand takeovers run `ariane verify` (no longer "once that command exists").
- [ ] All checks in CLAUDE.md pass.
- [ ] Definition of done, documentation (C25): `docs/reference/cli.md` regenerated with `verify`; `docs/architecture/` updated (`cli` and every module touched or added, the level 3 component and sequence views with `verify`); the README's usage section names `ariane verify`. While editing them, fix two points left by the review of #34: the first line of `modules/delivery.md` (a draft pull request can now carry failing checks) and the level 3 component view's missing `review_session` dependencies (`checks`, `config`, `tracker`).

## Out of scope

Pushing or opening the pull request (the human does), fix rounds.

## Related

ADR 0016, ADR 0020, spec C10, C23.
