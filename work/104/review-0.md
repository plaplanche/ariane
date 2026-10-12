# Review 0

- Reviewed commit: `533076c63a95dcb0df420b90a0651ff8c716419e`
- Reviewer model: claude-opus-5-5
- Verdict: **go**

## Findings

- **minor** (`src/ariane/verify.py:230`) verify can wrongly refuse a merge on the base branch when the local origin/<base> is out of date

  `remote_changes` runs in `repo_root` and calls `git.fast_forwarded`. That function returns False when the old base SHA (read with ls-remote when verify starts) is not in the local object store. `ariane verify` never fetches the base branch first, and `_base` uses whatever `refs/remotes/origin/<base>` it finds. So if the user's clone is behind the remote, someone merging to the base branch during verify gets the run refused as a non-fast-forward. That is the shared-repository case this ticket is about. `fast_forwarded` also updates the user's `refs/remotes/origin/<base>` as a side effect. Suggested fix: fetch the base branch first (or fetch `old` before testing it), and add a test with a stale local origin/<base>.

- **minor** (`tests/test_c11_remote_scope.py:121`) For verify, no test covers a non-fast-forward of the base branch

  The acceptance criterion asks for 'the same for `ariane verify`'. The verify tests cover another branch, the verified branch, a tag and a fast-forward of the base branch. A rewritten (force-pushed) base branch during verify is not tested, even though the flow tests cover it.

- **minor** (`tests/test_c11_remote_scope.py:141`) The last assertion of the verify fast-forward test always passes

  `assert git.remote_refs(...)["refs/heads/main"]` only checks that main exists, which is always true. It does not check that the base branch actually moved during the review. The test should compare main against its SHA before the review, so it cannot pass without the remote changing.

- **minor** (`docs/adr/0007-tracker-and-agent-runtime-interfaces.md:56`) ADR 0007 still says any branch or tag change on the remote stops the ticket

  ADR 0017 already revised this point and is amended here, so the history holds together. A short pointer in ADR 0007 to ADR 0017's amendment would stop readers from taking the old strict rule as current.

- **minor** (`tests/test_c11_remote_scope.py:20`) `acting` and `_push` take a `project` argument they never use

  Dead parameters make the helpers harder to read.

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

  In tests/test_c11_remote_scope.py, test_c11_remote_scope_another_branch_does_not_stop_the_ticket fails on the old code, which stopped on any ref. The three verify tests fail on the old code because verify had no remote check. The ticket-branch, tag, non-fast-forward and fast-forward tests use a real bare remote. That makes 8 tests matching -k c11_remote_scope, at least the 5 the checklist asks for, and all checks are green.

- met: The documentation the change affects is updated (C25).

  ADR 0017 has an amendment with the rule and why. docs/architecture/modules/flow.md lists `remote_changes`. docs/architecture/modules/verify.md describes the remote check in verify. docs/learnings.md entry 2 has an update. 'docs: references' is green. Only ADR 0007 still has the old wording, which is historical (minor).

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  The amendment to ADR 0017 records the choices left open: tag deletion also stops, verify compares from the start of the run to after the checks and after the reviewer, verify skips the check when there is no origin, and an agent creating some other branch is no longer detected.

## Proposed learnings (not decided)

- When a guard moves from one place (a ticket's working tree) to another (the user's main checkout in verify), check what it assumes about local state: `fast_forwarded` needs the old commit to be present locally.
- When a rule is relaxed, rewrite the old tests that relied on the wide rule (here: branch pushes changed to tag pushes) instead of deleting them, so the guard keeps its coverage.
- A test assertion that always passes, such as checking that a ref exists, hides whether the scenario under test actually happened; assert that the state changed.
