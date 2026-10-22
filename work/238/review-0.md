# Review 0

- Reviewed commit: `a7c8e0c6ef2c683481874fc11a562927220a04de`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`tests/test_c25_adr_numbers.py:32`) Documentation-only pull requests bypass the ADR collision check

  scripts/docs_only.py classifies every docs/adr/ change as documentation-only, and .github/workflows/ci.yml skips pytest for those pull requests. After one PR merges 0059-first.md, a later documentation-only PR adding 0059-second.md therefore passes CI without executing this assertion, even though its merge contains both files. This makes the check pass wrongly and defeats the ticket's promised merge-time detection. Ensure ADR changes run this validator even on the documentation-only CI path, and test that integration.

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

  Three named tests cover the repository, duplicate filenames and malformed names. Read-only execution using in-memory fixture files passed; disabling validation caused both negative tests to fail. Full pytest success is supported by Ariane's supplied replay.

- met: The documentation the change affects is updated (C25).

  docs/adr/README.md states the required renumbering and reference-update rule. Its CI detection claim has the integration gap reported above.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  The ticket explicitly decides the validation behavior and collision rule; no additional architectural choice requiring an ADR was identified.

## Proposed learnings (not decided)

- When adding a repository invariant test, check CI skip conditions as well as test discovery: documentation-only changes can violate documentation invariants.
