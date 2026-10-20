# Review 0

- Reviewed commit: `1554a309910f5f345decdeffc18e233fe5f1654c`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/flow.py:545`) Renaming a sensitive file suppresses owner-review delivery

  self.changed comes from git.changed_paths, which uses git diff --name-only and retains only the destination of a detected rename. With sensitive_paths=['src/ariane/git.py'], renaming that file to src/ariane/git_guard.py therefore produces no sensitive matches: delivery opens the PR without the required body warning and skips the owner-review label. The normal review correctly detects the old path through checks.changed_files(name_status), so review and delivery disagree. verify.py:359 has the same omission because changed comes from git.changed_between, also name-only. Confirmed read-only against an existing repository rename and the matching functions. Use the decoded, both-sided name-status paths consistently and add regression tests for renaming a sensitive file outside its matching glob.

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

  Eleven new test_c10_review_proportion_* tests cover base-only residuals, prompt rules, sensitive-path delivery, configuration, label refusal and verify. They depend on functionality absent before this change. Ariane reports the suite passing; tests were not rerun because their fixtures write files. Rename coverage is missing, as detailed in the finding.

- met: The documentation the change affects is updated (C25).

  README, affected architecture modules, configuration example, generated configuration schema and log catalogue are updated. The review-answer schema is unchanged. Ariane reports the generated-reference check passing.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0057 records marker continuation parsing, base-commit collection for start and verify, proportion exceptions, glob semantics, label timing and refusal handling.

## Proposed learnings (not decided)

- Use one decoded changed-path list, including both sides of renames, for review, verification and delivery; test a rename out of a sensitive glob.
