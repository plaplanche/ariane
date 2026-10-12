# Review 0

- Reviewed commit: `b6d4d9e392aed976c67e9e3edd72428504a66483`
- Reviewer model: claude-opus-5-5
- Verdict: **go**

## Findings

- **minor** (`docs/adr/0002-command-line.md:19`) Exit code list does not include the new 130

  ADR 0002 lists the command line's exit codes as 0, 1 and 2. This change adds 130 (EXIT_INTERRUPTED) for Ctrl-C in `start` and `verify`, but the ADR (and the README) were not updated or amended. The module docs (flow.md, verify.md) do describe the new code.

- **minor** (`tests/test_c5_interrupt.py:87`) Flow interrupt test does not check that the stop record was committed

  The ticket asks that the stop be committed 'like any stop'. The test checks the journal, status.md, the exit code and the line, but not that the worktree's HEAD holds the '#7: record the stop' commit. A regression where the record is written but not committed would still pass.

- **minor** (`src/ariane/verify.py:65`) verify records nothing on Ctrl-C, which reads differently from the ticket

  The ticket says `ariane verify` records the stop when the ticket folder exists. In verify, the records folder is a temporary directory that is never committed on any stop (a Refused also commits nothing). So doing nothing is consistent with verify's existing behaviour, and verify.md documents it. It is still a reading of the spec worth confirming with the owner.

- **minor** (`src/ariane/git.py:373`) Unrelated refactor included

  `remote_changes` moved from flow to git, and verify no longer imports it from flow. The move is correct: no stale callers are left, and flow.md and git.md are updated. It is outside the ticket's scope, though, and makes the diff bigger.

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

  test_c5_interrupt_kills_the_process_tree_and_reraises: KeyboardInterrupt is raised from Popen.wait. Without the `finally`, kill_tree is skipped and the parent and grandchild, which sleep 60 s, stay alive, so the assertion fails. test_c5_interrupt_during_the_agent_session_is_recorded_and_exits_130 and the before-folder and verify tests would see an uncaught KeyboardInterrupt without the new except clauses. Four tests match -k c5_interrupt (one is skipped on Windows).

- met: The documentation the change affects is updated (C25).

  process.md documents the finally cleanup. flow.md documents the interruption and EXIT_INTERRUPTED. verify.md documents verify's Ctrl-C behaviour. git.md and flow.md reflect the remote_changes move. No log event was added, so the catalogue needs no regeneration ('docs: references' is green). Minor gap: the exit-code list in ADR 0002 is not amended.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  The ticket's decided spec sets the behaviour: finally, the 'interrupted by the user' wording, recording the stop, exit 130. The one interpretation, that verify commits nothing, follows verify's existing behaviour under ADR 0028 and is documented in verify.md. No new open design choice needs its own ADR.

## Proposed learnings (not decided)

- When a change adds an exit code, also amend the ADR that lists the exit codes (ADR 0002), not only the module docs.
- Tests of 'recorded like any stop' should check the commit, not just the files written in the working tree.
