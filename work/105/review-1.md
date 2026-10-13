# Review 1

- Reviewed commit: `68215d397d9d86826f5c1b0f6d45b85e6fbf3e1b`
- Reviewer model: claude-opus-5-5
- Verdict: **go**

## Findings

- **minor** (`src/ariane/verify.py:88`) verify's next action for a plain tracker error got less specific

  Before this change, a failed `verify --issue` read said "Next: check the issue number". It now passes through `TrackerError.next_action`, which is "check the number" (the wording `start` uses). This is a small change in user-facing wording that the ticket did not ask for. No test pins either text.

- **minor** (`src/ariane/github.py:76`) Events pagination and the GHES GraphQL endpoint are untested

  `_check_trusted` follows `page=N` until a short page comes back, and `__init__` maps `/api/v3` to `/api/graphql` for GitHub Enterprise Server. No test covers either. Paging matters for security: a labelled event or rename on page 2 that is missed would be ignored, though a missed later `labeled` event fails closed only by luck. Add one test with more than 100 events and one for the GHES root.

- **minor** (`src/ariane/tracker.py:20`) Exit 2 is shared with argparse usage errors

  `IssueRefused.exit_code = 2` is the same as `cli.EXIT_USAGE = 2`, so a script cannot tell a refused issue from a bad command line. The ticket's spec chose exit 2, so this is not a defect, but the overlap may be worth recording in the ADR.

- **minor** (`src/ariane/github.py:64`) `label` parameter duplicates `self._ready_label`

  `_check_trusted(number, data, self._ready_label)` passes a value the method can already read from `self`. This is harmless but redundant.

## Definition of done

- met: check lint passes

  Replayed by Ariane: exit 0.

- met: check format passes

  Replayed by Ariane: exit 0.

- met: check types passes

  Replayed by Ariane: exit 0.

- met: check tests passes

  Replayed by Ariane: exit 0.

- met: check file length passes

  Replayed by Ariane: exit 0.

- met: The change is covered by tests that fail without it.

  `tests/test_c21_issue_gate.py` adds 16 `test_c21_issue_gate_*` tests against a fake HTTP GitHub server. They cover every case the ticket asks for: accepted when labelled by a writer, maintainer or admin; refused without the label; refused when labelled by a reader; uses the last `labeled` event; body edited by a reader after the label is refused, by a writer is accepted, by a reader before the label is accepted; rename by a reader is refused, by a writer is accepted; a configured label is used; `ready_label` is read from the configuration; `flow.start` returns exit 2 with no branch or worktree; the CLI `start` and `verify --issue` exit 2 and create nothing; a user with no permission record is refused. They import `IssueRefused` and pass `ready_label=`, neither of which exists on the base, and the base never makes the events, permission or GraphQL calls, so they fail without the change. `tests/test_github.py` was adapted to the new gate.

- met: The documentation the change affects is updated (C25).

  Updated: ADR 0032; module docs `github.md`, `config.md`, `tracker.md`, `cli.md`, `flow.md` and `verify.md`; the regenerated `docs/reference/ariane.toml.schema.json` (matches `config_schema.py`, and the docs: references check passed); `docs/ariane.example.toml`; `ariane.toml`; the README paragraph telling the owner to add the label. Ariane flagged `docs/architecture/modules/config_schema.md` as untouched. It describes the schema's structure, runtimes and reviewer if/then rules, not individual tracker keys, so the new key does not need a mention there. No new log event, so the log catalogue is unaffected. `docs/spec.md` does not list tracker keys.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  `docs/adr/0032-issue-gate.md` records the rule and its alternatives (an author allow list, no check). It also records the choices the ticket left open: an edit in the same second as the label counts as after it; a missing actor or deleted account has no permission; the GraphQL endpoint derivation for GHES; only the last body edit is visible.

## Proposed learnings (not decided)

- A security gate that pages through API results needs a test with more than one page, or a missed page silently weakens the gate.
- When a refusal class carries its own exit code and next action, check that callers which used to hard-code their own message did not lose specific wording.
- A module doc mapped to a changed file (here config_schema.md) need not change when it describes structure rather than individual keys; say so explicitly in the review.
