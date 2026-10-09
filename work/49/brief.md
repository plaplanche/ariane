# Product brief: Align records and ADRs with the delivered code (C1, C11, C23)

- Source: issue #49 (https://github.com/plaplanche/ariane/issues/49)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

The independent review of slice 2 found records and ADRs that do not say what the code does. Spec C1, C11, C23; ADRs 0005, 0017, 0019; CLAUDE.md rule 2 (a choice is recorded in an ADR).

## Current state

- `src/ariane/git.py` `push` (#30): when the push with the token header is refused for authentication, or no token is set, Ariane pushes once more without the header (a cloud sandbox's proxy may supply credentials). The README says so; ADR 0017 does not.
- `src/ariane/cli.py` `_merged` (#28) reports `merged` when `work/<n>/` exists on the remote base branch; ADR 0019 says "when the ticket branch's head is contained in the base branch on the remote". The code's way also works after a squash merge.
- `src/ariane/context.py` `implementer_prompt(recorded=True)` (#27) writes `(issue #<n> title and body: see brief.md)`; ADR 0019 asks for "see brief.md, read at <time>".
- `src/ariane/delivery.py` `deliver` writes and commits `status.md` as "delivered / pull request from ariane/<n> / review and merge the pull request" before the push and before the pull request is opened; if the tracker refuses the pull request, the pushed status still claims one. ADR 0019: the file "never claims what Ariane cannot know".
- ADR 0005 names the workflow, the script and `ariane.toml` as what runs with the workflow's token in `check-statuses.yml`; the branch's `src/ariane`, `pyproject.toml` and `uv.lock` run with it too.

## Decided spec

- ADR 0017 gains a paragraph on the fallback push: when, how many times (once), with the credential helpers still disabled, journaled.
- ADR 0019 says `merged` means `work/<n>/` is on the remote base branch, and why (records travel with the pull request; squash merges).
- The recorded prompt's pointer becomes `(issue #<n> title and body: see brief.md, read at <time>)`, with the time the issue was read.
- The pushed `status.md` says `Last action: pushed`, `Detail: ariane/<n> pushed; opening the pull request`, `Next: see the pull request, or run ariane status <n>`.
- ADR 0005's trust paragraph names `src/ariane`, `pyproject.toml` and `uv.lock` among what runs with the token.

## Release note

Fixed: the pushed status no longer claims a pull request before it is opened.

## Acceptance criteria

- Tests named `test_c1_records_pointer_has_read_time_*` and `test_c11_pushed_status_*` cover the two code changes.
- The three ADRs are updated as above.
- All checks in CLAUDE.md pass.

## Acceptance checklist

- [ ] `uv run pytest -k "c1_records_pointer_has_read_time or c11_pushed_status"` runs at least 2 tests and they pass.
- [ ] ADRs 0005, 0017 and 0019 carry the changes.
- [ ] All checks in CLAUDE.md pass.

## Out of scope

The docs-only CI detection (separate issue, workflow file).
