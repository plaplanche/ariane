# Review 0

- Reviewed commit: `b14746753e58ef3eaffa572c8f8e0a5456c45bcb`
- Reviewer model: claude-opus-5-5
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/verify.py:58`) The new `ariane verify` interrupt path has no test

  `verify()` now catches KeyboardInterrupt and returns EXIT_INTERRUPTED (130) with its own line. No test covers this: both `test_c5_interrupt_*` tests go through `process.run` or `flow.start`. If the new `except KeyboardInterrupt` branch were deleted, every test would still pass, so the definition of done ('covered by tests that fail without it') is not met for this part of the change. Add a `test_c5_interrupt_*` test where the reviewer runtime (or setup) raises KeyboardInterrupt during verify. It should assert exit 130, the 'interrupted by the user' line, that the replay worktree was removed and that nothing was committed.

- **blocking** (`docs/architecture/modules/verify.md:7`) verify.md is not updated for the new interrupt behaviour

  Rule 11 / C25 requires the `modules/<module>.md` of every module touched to be updated. Ariane also flagged this file as mapped but not touched. verify.py gained a new outcome (Ctrl-C gives exit 130, 'Stopped verifying <branch>: interrupted by the user', no records committed), but verify.md still lists only exit 0 for a green `go` and exit 1 for the other cases. Document the interrupt outcome here.

- **minor** (`docs/architecture/modules/flow.md:15`) flow.md says verify reports 'the same line', which is wrong

  flow.md says `ariane verify` 'reports the same line and code'. It does not: verify prints 'Stopped verifying <branch>: interrupted by the user. Next: run verify again.' and records nothing in a journal or status.md, because its records folder is a temporary directory. Describe verify's behaviour in verify.md and keep flow.md accurate.

- **minor** (`src/ariane/flow.py:73`) Ctrl-C before `_TicketRun.execute` still ends in a traceback

  KeyboardInterrupt is caught only inside `execute`. A Ctrl-C during `tracker.read_issue` or `_prepare` (which includes `git fetch` and `git ls-remote`, which can take a while) reaches `cli.main` unhandled, so Python prints a traceback instead of 'one line, exit 130'. At that point the ticket folder does not exist yet, so there is nothing to record. The command should still print one line and exit 130, either by catching it in `start` next to the `Stop`/_FAILURES handler or in `cli`.

- **minor** (`src/ariane/process.py:168`) On an exception the killed child is not reaped

  When the wait raises (KeyboardInterrupt or another error), the `finally` kills the tree, but the drain `proc.wait(timeout=_DRAIN_SECONDS)` is skipped. The direct child stays a zombie until the Popen object is garbage-collected, and the reader threads are not joined. This is harmless for a process that is exiting, but a best-effort reap in the `finally` (with the TimeoutExpired suppressed) would close the gap.

- **minor** (`tests/test_c5_interrupt.py:67`) The process-tree test is skipped on Windows and macOS

  The real-tree test is skipped wherever /proc is missing, so the CI runs on Windows and macOS do not exercise the kill. The macOS case could check liveness with `os.kill(pid, 0)` plus `os.waitpid` or `ps` instead of /proc. Windows uses the separate taskkill path and has no coverage.

- **blocking** Definition of done not met: The change is covered by tests that fail without it.

  Two parts are covered. `test_c5_interrupt_kills_the_process_tree_and_reraises` would fail without the `finally` in `process._execute` (the tree would survive), and `test_c5_interrupt_during_the_agent_session_is_recorded_and_exits_130` covers the `flow` changes (`_describe`, the KeyboardInterrupt catch, EXIT_INTERRUPTED). The `except KeyboardInterrupt` added in `verify.verify` has no test, and the real-tree test is skipped on macOS and Windows.

- **blocking** Definition of done not met: The documentation the change affects is updated (C25).

  process.md and flow.md are updated, as the ticket's checklist asks. No log event was added, so the catalogue needs no regeneration. verify.md, the module doc of the touched verify.py, is not updated for the new exit-130 outcome, and flow.md describes verify's line incorrectly ('the same line').

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

  Two parts are covered. `test_c5_interrupt_kills_the_process_tree_and_reraises` would fail without the `finally` in `process._execute` (the tree would survive), and `test_c5_interrupt_during_the_agent_session_is_recorded_and_exits_130` covers the `flow` changes (`_describe`, the KeyboardInterrupt catch, EXIT_INTERRUPTED). The `except KeyboardInterrupt` added in `verify.verify` has no test, and the real-tree test is skipped on macOS and Windows.

- **not met**: The documentation the change affects is updated (C25).

  process.md and flow.md are updated, as the ticket's checklist asks. No log event was added, so the catalogue needs no regeneration. verify.md, the module doc of the touched verify.py, is not updated for the new exit-130 outcome, and flow.md describes verify's line incorrectly ('the same line').

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  The ticket's 'Decided spec' fixes the behaviour (a `finally` around the wait, exit 130, 'interrupted by the user'). The remaining choices, such as the next-action wording, are cosmetic, so no new ADR is needed.

## Proposed learnings (not decided)

- When a ticket names two commands (start and verify), check that each has its own test and its own module doc. Here the second command (verify) got code but no test and no doc update.
- Catching KeyboardInterrupt in only one layer leaves earlier phases (fetching the issue, preparing the worktree) printing a traceback. Check every phase of a command against 'print one line, exit 130'.
- Tests that need /proc are skipped silently on macOS and Windows CI. Prefer liveness checks that work on every platform when the check is part of an acceptance criterion.
