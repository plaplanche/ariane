# Review 2

- Reviewed commit: `4a8bafd42c024e419cf1648cec60795515e4e671`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/process.py:87`) Subreaper initialization fails open

  If Linux rejects PR_SET_CHILD_SUBREAPER, this handler logs a warning and returns normally; cli.main then starts tickets without the prerequisite for descendant cleanup. The sequence is: initialization fails, warning is written, an agent starts a detached child and exits, the child is reparented outside Ariane, and both cleanup scans miss it. The survivor is neither killed nor counted, and review can proceed while it continues writing files. A read-only mock probe confirmed that an EPERM result returns None without stopping execution. Refuse agent/setup/check execution when Linux subreaper initialization fails, and test that failure path.

- **minor** (`src/ariane/review.py:238`) Quoted binary paths are corrupted in the truncation notice

  The header fallback assumes two unquoted paths with identical lengths. Git quotes paths containing tabs, quotes or backslashes even with core.quotepath=off. A read-only probe using a binary diff for a filename containing a tab returned '/a\\tb.bin"' instead of the filename. The complete name-status block remains available, but the missing-hunk notice and journal direct the reviewer to an incorrect path. Parse Git's quoted header format and add quoted binary and mode-only cases.

- **blocking** Definition of done not met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0031 records snapshot timing, runtime-specific files, survivor scanning, its deadline, timeout treatment, stopped verification metrics, and platform residuals. However, continuing on Linux when subreaper initialization fails is documented only in code and the module reference, not as an ADR decision, and undermines the ticket's required guarantee.

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

  The new test_c10_reviewer_integrity tests exercise instruction-file tampering, complete changed-file lists and truncation disclosures, detached and ordinary background children, setup ordering, interruption, and stopped-run metrics. These assertions depend on newly added behavior. Ariane reports the test suite passed; I did not rerun filesystem-writing tests in this read-only review. Initialization failure and quoted binary paths remain uncovered.

- met: The documentation the change affects is updated (C25).

  README, ADR 0031, the affected workflow and module documents, component relationships, and the generated log catalogue were updated. The unchanged logs module document describes the generic logging API and links to the updated catalogue; its existing description remains applicable.

- **not met**: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0031 records snapshot timing, runtime-specific files, survivor scanning, its deadline, timeout treatment, stopped verification metrics, and platform residuals. However, continuing on Linux when subreaper initialization fails is documented only in code and the module reference, not as an ADR decision, and undermines the ticket's required guarantee.

## Proposed learnings (not decided)

- Proposed: test failure to initialize a security prerequisite, and prevent protected work from starting when initialization fails.
- Proposed: test Git path parsing with quoted names and header-only changes, not only ordinary text hunks.
