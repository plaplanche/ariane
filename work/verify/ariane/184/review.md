# Review 0

- Reviewed commit: `0ec3c7650665cdeb7f386867de54631d49a1e483`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/checks.py:91`) An opened records directory can move outside the tree before the listing is written

  The POSIX implementation does not provide its claimed containment guarantee. Interleaving: worker A opens tree/work/7 and retains its directory descriptor; a concurrently running check B renames that directory to a location outside the replay tree on the same filesystem; A then creates changed-files.txt relative to the retained descriptor and writes the listing there. Directory descriptors follow the opened directory across renames, and O_NOFOLLOW only prevents following symlinks. Moving work after it is opened can likewise make the subsequent mkdir('7', dir_fd=fd) write outside the tree. Verification occurs after these writes and cannot prevent them; removing the replay tree does not remove the escaped listing. The new race tests swap directories immediately after mkdir, before open, so they miss this interleaving. Add coverage for moving an already-open directory outside the tree and enforce the promised containment against concurrent mutations.

- **minor** (`docs/architecture/modules/replay.md:26`) Replay documentation describes cleanup that no longer happens

  This paragraph says the listing is removed after the check through directory handles so verification sees no new file. changed_files_listing deliberately leaves it in place, and verify filters its path with without_listing before removing the whole tree. Update this paragraph and the _run_check docstring to describe the implemented lifecycle, consistent with ADR 0056.

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

  tests/test_c9_selective_checks.py contains more than six named tests covering selection, rename sources, configuration overrides, schema rejection, changed-file contents, skipped reports, statuses, PR bodies and reviewer prompts. These exercise APIs and behavior absent before the change. Ariane reports the full suite green; I did not rerun filesystem-writing tests in this read-only review. The already-open-directory race remains uncovered. Write-order audit: ticket replay journals selection and parallelism, creates each selected worktree and Git metadata, copies/builds caches and conditionally stores them after validation, runs setup and its guards, creates listing directories and the listing, executes the check, verifies, removes the tree, then writes replay journals and checks.md. Skipped checks create no tree and execute no command. Review creates its tree, writes session records, verifies, writes the review result and removes its tree. Delivery writes delivery records and commits them, checks replay consistency and the final guard, pushes, journals the push, opens the PR, journals delivery, publishes statuses, then writes and commits the local delivery record. Verify uses the same selected-check lifecycle, creates temporary records, reviews and verifies, writes report/metrics records, checks before committing, commits them, and removes temporary records; refusal retains stopped metrics. The blocking finding identifies the listing writes that can escape before verification.

- met: The documentation the change affects is updated (C25).

  The required module documentation, component view, README, example configuration, generated schema and log catalogue are updated. The remaining lifecycle inconsistency is identified as a minor finding.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0056 records the default selection policy, configuration override, file-based environment contract, rename handling, exclusion of work records, unsupported filename handling, listing lifecycle, platform differences and reuse of the round's diff. Its asserted POSIX containment guarantee is not achieved by the implementation.

## Proposed learnings (not decided)

- Proposed: Directory handles prevent symlink substitution but do not pin a directory's ancestry; containment tests should move already-open directories outside the allowed tree.
- Proposed: When cleanup changes from deleting an artifact to filtering it during verification, update lifecycle documentation and test both replay entry points.

## Run

Slot 0 (`ARIANE_SLOT=0` for the setup, the checks and the reviewer, ADR 0050).
