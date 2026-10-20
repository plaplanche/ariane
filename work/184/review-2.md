# Review 2

- Reviewed commit: `af6c2987a83fff31112208281454a5f278b1b1a3`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/checks.py:109`) Listing identity check and deletion are not atomic

  The write order is: create replay tree, run cache/setup writes, create and write the listing, run the check, stat the listing, compare its identity, unlink its name, verify, remove the tree. Between the identity comparison and unlink, another parallel check can rename the original listing and replace it with another file. Ariane then deletes the replacement despite the ADR's promise to remove only the file it wrote. A directory handle pins the parent, not the directory entry being deleted. The existing concurrency test swaps the parent directory, so it misses this interleaving. Cleanup needs an ownership strategy that remains safe under replacement, with a regression test swapping the file itself.

- **blocking** (`src/ariane/checks.py:47`) Unicode line separators silently remove matching paths from selection

  splitlines() treats Unicode separators such as U+2028 as record boundaries, although git with core.quotepath=off can emit them literally inside filenames. A read-only reproduction using 'M\tsrc/name\u2028tail.py' produced ['src/name']; a check scoped to src/**/*.py was skipped, and unlistable() returned no error. git.changes also splits the raw listing this way, so fixing only this function is insufficient. Preserve Git's actual record boundaries throughout parsing, then reject unsupported names before selection. Otherwise a changed Python file receives a successful skipped status and ARIANE_CHANGED_FILES contains the wrong path.

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

  Sixteen named test functions, plus parameterized cases, cover selection, schema validation, renamed paths, listing contents, skipped reports, statuses and reviewer prompts. These exercise new behavior absent from the base. Ariane reports the suite passed; the two identified edge cases lack coverage.

- met: The documentation the change affects is updated (C25).

  README, the example configuration, affected architecture modules, generated schema and log catalogue are updated. The cleanup guarantee needs correction alongside the race fix.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0056 records defaults, configuration overrides, file-based transport, per-round selection, filename restrictions, cleanup strategy and platform differences.

## Proposed learnings (not decided)

- Proposed: Test replacement of the final directory entry as well as replacement of its parent when reviewing filesystem cleanup races.
- Proposed: Parse Git records using their explicit delimiters; Python splitlines() recognizes separators that may belong to filenames.
