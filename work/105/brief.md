# Product brief: Only run issues labelled by a maintainer and not edited by anyone else since (C21, C22)

- Source: issue #105 (https://github.com/plaplanche/ariane/issues/105)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

Ariane reads any issue it is given: the repository is public, anyone can open or edit an issue, and its title and body become the implementer's task, run with `bypassPermissions` and a shell. The untrusted-data tags are not a boundary. An outside analysis of 2026-10-11 rates it high (prompt injection by the issue). The owner decided: Ariane only reads an issue that carries a label put by a person with write access, and not edited by anyone else after that. Spec: C21, C22, C1.

## Current state

- `src/ariane/github.py:43` `read_issue`: one `GET /repos/{repo}/issues/{n}`, title and body taken as they are, no check of author, label or edits.
- `src/ariane/config.py:188`: `[tracker]` accepts `kind`, `repository`, `token_env`, `api_url`.

## Decided spec

- `[tracker]` gains `ready_label` (string, default `"ariane"`).
- Before reading the task, Ariane checks, through the GitHub API:
  1. the issue carries `ready_label`;
  2. the last time that label was added (issue events, `labeled`), it was added by a user whose permission on the repository is `write`, `maintain` or `admin` (`GET /repos/{repo}/collaborators/{user}/permission`);
  3. after that moment, the title and the body were not changed by anyone without that permission (title: `renamed` events; body: the issue's last edit, read with the GraphQL field `lastEditedAt` and `editor`).
  Any check failing refuses the issue with one line naming the reason and how to fix it ("ask a maintainer to add the label `ariane` again after the last edit"), exit 2, before any branch, worktree or agent.
- This applies to `ariane start` and to `ariane verify --issue`.
- A new ADR (next free number) records the rule and its alternatives (author allow list, no check).
- `docs/ariane.example.toml`, `ariane.toml` (this repository uses the label `ariane`) and README are updated; the README tells the owner to add the label to the tickets to run.

## Release note

Security: Ariane only runs an issue labelled by a maintainer and not edited by anyone else since.

## Acceptance criteria

- Tests named `test_c21_issue_gate_*` with a fake GitHub server show: accepted when labelled by a writer and not edited after; refused without the label; refused when labelled by a reader; refused when the body was edited by a reader after the label; accepted when edited by a writer after the label; refused when renamed by a reader after the label; nothing is created (branch, worktree) on a refusal; `ready_label` read from the configuration.
- All checks in CLAUDE.md pass.

## Acceptance checklist

- [ ] `uv run pytest -k c21_issue_gate` runs at least 7 tests and they pass.
- [ ] All checks in CLAUDE.md pass.
- [ ] Definition of done, documentation (C25): new ADR, `github.md` and `config.md` module docs, regenerated reference schema, example configuration, README.

## Out of scope

Reading issue comments (agents never read them); other trackers.

## Related

ADR 0013, ADR 0021, spec C21, C22, slice 4 prerequisites.
