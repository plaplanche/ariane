# Review 0

- Reviewed commit: `a831b23e657a126a31d75500864c458051fb380a`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/checks.py:36`) Decode Git-quoted filenames before selecting checks

  git.changes returns non-NUL-delimited raw paths. Git quotes filenames containing double quotes, backslashes or control characters even with core.quotepath=off. changed_files preserves that quoting: a changed file named src/a"b.py becomes a string starting with a quote, so paths=['src/**'] does not match. A read-only probe confirmed the check is omitted. Ariane then records a skipped success for a check that should run, and ARIANE_CHANGED_FILES contains an encoded spelling rather than the actual path. Parse lossless Git paths and add regression coverage for quoted paths, including rename sources.

- **blocking** (`src/ariane/replay.py:194`) Cleanup can delete a file outside the replay tree

  The selected-check path orders its effects as tree creation, cache/setup writes, containment check, directory creation, listing creation/write, check execution, listing unlink, post-check verification, and tree removal; replay logs follow. The containment check precedes execution, but unlink resolves the parent directories again afterward. A check can rename work/7 and replace it with a symlink to an external directory containing changed-files.txt; the finally block then deletes that external file before verify(tree) runs. This requires no surviving process or concurrent race. Bind cleanup to the original directory/file safely, and test parent replacement during check execution.

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

  The new selective-check tests exercise selection, skipped reports/statuses/prompts, configuration validation, rename sources and changed-file delivery, using behavior absent from the base. Ariane reports passing checks. I inspected the tests and ran read-only probes; I did not rerun filesystem-writing tests. The edge cases in the findings remain uncovered.

- met: The documentation the change affects is updated (C25).

  README, the example configuration, affected module documentation, component view, generated configuration schema and log catalogue are updated.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0056 records selection defaults, configuration overrides, rename handling, work-directory exclusion, temporary listing lifecycle, skipped results and statuses, and reuse of the round's diff.

## Proposed learnings (not decided)

- Proposed: use lossless Git path parsing for decisions that can skip required checks.
- Proposed: filesystem containment established before untrusted execution must not be assumed valid during cleanup.
