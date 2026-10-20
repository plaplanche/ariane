# Review 2

- Reviewed commit: `97eaf20110cce408ae3ceb738637801382e6970e`
- Reviewer model: gpt-6-astra
- Verdict: **go**

## Findings

- **minor** (`src/ariane/review.py:249`) Start and verify select different ADR files

  residuals_in reads only immediate *.md children, whereas accepted_residuals searches every tracked file recursively under docs/adr/. A marked residual in docs/adr/archive/0001-guard.md therefore reaches verify but not start or shadow. Align the selection rules and add a parity test. The repository's current flat ADR layout is unaffected.

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

  The new tests assert base-only residuals, prompt rules, sensitive-path labels and body text, nonmatching paths, label refusal, configuration, verify, renames and symlink exclusion. These assertions depend on the new behavior. Ariane reports the tests passing; I did not rerun write-producing tests in this read-only review.

- met: The documentation the change affects is updated (C25).

  README, configuration example and schema, affected architecture modules, log catalogue and residual ADRs are updated. Ariane reports generated-reference checks passing; the review-answer schema is unchanged.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0057 records marker continuation parsing, base-commit capture, proportion exceptions, rename matching, label timing and refusal handling, and unchanged verdict settlement.

## Proposed learnings (not decided)

- Proposed: when filesystem and Git readers implement the same policy, test that both select the same files and produce identical results.
