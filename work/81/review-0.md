# Review 0

- Reviewed commit: `ba3136672fc28bdb8e5255e9652e189fe422a3b8`
- Reviewer model: claude-opus-5-5
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/flow.py:570`) git.commit now silently returns False for ignored paths, and flow's _commit_record ignores that

  git.commit used to raise GitError when `git add` failed, for example when the project ignores work/. Now it returns False when the add output contains "ignored". verify checks that result, but flow._commit_record (flow.py:570) still drops it. A ticket run in a project that ignores work/ used to stop loudly. Now it goes on and delivers a pull request without its records (journal, checks.md, review.md). That is the same 'records reported but not committed' bug this ticket fixes in verify, moved into the main flow. No test covers it. Fix: make flow raise or stop when the records commit returns False, or keep the lenient behaviour local to verify.

- **minor** (`tests/test_verify.py:160`) The 'committed to during the run' test does not exercise _before_commit

  The racing commit happens inside a review action, so the existing `_unchanged` callback after the reviewer already catches the moved branch ('the reviewer moved a head'). The test only asserts 'Did not verify', so it passes without the new `_before_commit` check. The re-check in `_before_commit` for the branch having moved is untested, and so is its check for uncommitted changes in the tree where the branch is checked out.

- **minor** (`src/ariane/git.py:272`) Detecting ignored paths depends on git's English message

  The `"ignored" not in added.output` test assumes git's English output; git is not run with LC_ALL=C. With a localized git, an ignored work/ raises GitError instead of giving the 'nothing was recorded' message. It still fails rather than reporting success, but the guidance the ticket asks for is lost.

- **minor** (`docs/architecture/modules/git.md:12`) git.md not updated for the new commit behaviour

  `commit` now returns False when every path is ignored and raises GitError on any other `git add` failure. Ariane flagged git.md as a mapped document that was not updated, and it still lists `commit` among 'history queries' with no mention of this.

- **blocking** Definition of done not met: The change is covered by tests that fail without it.

  The stdin, role-env, cli._runtime, ignored-work/ and checked-out-elsewhere tests would fail without the change. The 'branch committed to during the run' test passes without it, because the existing _unchanged callback catches the move. The dirty-tree re-check is untested, and so is the change in flow's behaviour for an ignored work/.

- **blocking** Definition of done not met: The documentation the change affects is updated (C25).

  ADR 0029 and modules opencode.md, runtime.md, flow.md, review_session.md, verify.md and process.md are updated. git.md is not, although git.commit's contract changed.

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

- **not met**: The change is covered by tests that fail without it.

  The stdin, role-env, cli._runtime, ignored-work/ and checked-out-elsewhere tests would fail without the change. The 'branch committed to during the run' test passes without it, because the existing _unchanged callback catches the move. The dirty-tree re-check is untested, and so is the change in flow's behaviour for an ignored work/.

- **not met**: The documentation the change affects is updated (C25).

  ADR 0029 and modules opencode.md, runtime.md, flow.md, review_session.md, verify.md and process.md are updated. git.md is not, although git.commit's contract changed.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0029 is amended for standard input and one environment per role. The verify behaviour was decided in the issue itself.

## Proposed learnings (not decided)

- When a shared helper's error contract changes (raise becomes return False), check every caller, not only the one the ticket names.
- A test for a new late re-check must make the change happen after the earlier guards have run, or it proves nothing about the new code.
- Do not match on git's human-readable output without forcing LC_ALL=C.
