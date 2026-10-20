# Review 0

- Reviewed commit: `8f689a04cebadc0b9e7c905de90d4c35531d327b`
- Reviewer model: gpt-6-astra
- Verdict: **go**

## Findings

None.

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

  The new recording test requires three PID-named files and no shared output file; the old helper fails these assertions. The new template test checks all three maintenance settings in both repositories using the template configuration; the old fixture lacks these settings. Existing assertions remain unchanged. Ariane reports all replayed checks passing. Tests were not rerun in this read-only review; the five pull-request CI jobs were not independently verified.

- met: The documentation the change affects is updated (C25).

  ADR 0049 documents the three maintenance settings and their application before the first Git command. Only test helpers changed; no production module documentation is affected.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  The implementation follows the ticket's explicit decisions without introducing additional behavioral choices. ADR 0049 records the maintenance configuration. Write-order review: create template directory, write isolated configuration, initialize bare repository, clone, checkout, write fixture files, stage, commit, push, return template; subsequently copy remote, copy checkout, rewrite only the copied origin URL. Every template Git command receives the configuration established beforehand. Recording processes sleep, create their own PID-named file, write one JSON record, close and exit; callers wait for completion before reading sorted files. The SLOW helper already uses distinct output paths. No conflicting shared writes or new retry paths were found.

## Proposed learnings (not decided)

- Give concurrent test processes separate result files instead of relying on cross-platform append atomicity.
- Disable automatic Git maintenance before constructing a repository template that will later be copied.
