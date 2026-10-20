# Review 1

- Reviewed commit: `1ab08dad2106de61f72bf61f656412797169aef6`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/replay.py:176`) Changed-files creation and cleanup have filesystem races

  The write sequence is: create replay tree, run cache/setup writes, check containment, mkdir, check absence, create/write listing, run check, check folder/file identities, unlink listing, verify, remove tree, write journal/report records. With parallel checks, another active check can replace work/<n> with an outside-directory symlink after containment is checked but before mkdir/open; exclusive creation protects the final filename, not its parents. Likewise, replacing the parent after the identity checks at lines 204–205 but before unlink at line 206 deletes an outside changed-files.txt. Verification happens after these writes and cannot prevent them. Bind creation and cleanup to securely opened directory handles or an equivalent mechanism, and add deterministic interleaving tests. The existing test swaps folders before cleanup starts and misses these races.

- **blocking** (`src/ariane/checks.py:70`) A newline in a filename silently skips its scoped check

  git_path decodes escaped newlines into actual filename characters, but matching_paths compiles ** as .* without DOTALL. A read-only probe confirmed that src/ordinary.py matches src/** while the valid Unix filename src/line\nbreak.py does not. A ticket changing only that file therefore skips its scoped check and publishes success. The newline also becomes an extra record when the filename is written into changed-files.txt, so consumers receive two apparent paths. Make wildcard matching cover these filenames and explicitly handle names that cannot be represented by the line-delimited protocol, stopping safely rather than supplying an ambiguous list. Add regression coverage.

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

  The new selective-check tests exercise skipping, statuses, reports, selection, renames, schema validation and the changed-files environment variable; these depend on the new behavior. Ariane reports the suite passing. The concurrency and newline cases identified above remain uncovered; filesystem-writing tests were not rerun during this read-only review.

- met: The documentation the change affects is updated (C25).

  README, the example configuration, affected architecture modules, generated schema and log catalogue are updated. The supplied generated-reference check passed.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0056 records defaults, configuration overrides, diff reuse, rename handling, file-based transport, cleanup, reporting and verify behavior. Its filesystem safety guarantees need the implementation corrections above.

## Proposed learnings (not decided)

- Proposed: Test filesystem safety with swaps between validation and mutation, including another active replay worker.
- Proposed: Test changed-path selection and transport with control characters; unsupported filenames must fail explicitly rather than silently reduce verification.
