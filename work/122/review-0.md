# Review 0

- Reviewed commit: `fc0af4031398158a90ec748dc76f4cbac380ec43`
- Reviewer model: claude-opus-5-5
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`docs/architecture/3-components.md:183`) The `start --shadow` sequence does not match the code: no replay, no review_session

  `ShadowRun` (src/ariane/shadow.py:91) is a subclass of `flow._TicketRun` and overrides only `_remote_changes` and `_deliver`. Its implementer session, metrics, commit, replay and review all run through `_TicketRun._check_and_deliver`, which calls `replay.replay` and then `replay.review_round` → `ReviewSession` (flow.py:423-445, replay.py:74). The new diagram instead shows `shadow` calling `checks`, `runtime`, `review`, `metrics` and `git` directly (`H->>C: replay the checks`, `H->>R: run a read-only reviewer session`, `H->>V: validate the answer`). The decided spec says this sequence has "the same implementer, replay and review steps", so it should go through `flow`/`replay`/`review_session` like the `start` sequence does. This is the same drift (direct calls to checks and runtime) that the ticket fixes in the `start` sequence. The new test misses it because `shadow` imports `checks`, `review`, `runtime.AgentRuntime` and `metrics.METRICS` for types or constants only. Redraw it as shadow → flow run (ShadowRun) → replay → review_session, or reuse the `start` sequence with the delivery step replaced by the local record.

- **minor** (`docs/architecture/3-components.md:255`) `report` does not read pull request states from the tracker itself

  report.build only hands the tracker on to `measures.human(d, tracker, takeovers)` (report.py:60). The pull request states are read by `measures`, not by `report`. The arrow `P->>T: read pull request states` passes the check only because report imports `Tracker`. `E->>T` (with measures as the caller) would be accurate, if measures imports the tracker.

- **minor** (`tests/test_docs_sequences.py:11`) The arrow regex skips activation and async forms of solid calls

  `^\s*(\w+)->>(\w+):` does not match `A->>+B:`, `A->>-B:`, `A-)B:` or `A-xB:`, so a future sequence that uses activations would go unchecked without any error. The participant regex also ignores participants that are declared implicitly (no `participant` line) and `create participant`. Either accept `->>[+-]?` or fail on arrow forms it does not recognise.

- **minor** (`tests/test_docs_sequences.py:33`) Problems name only the file's base name

  `path.name` drops the subfolder (`modules/x.md` shows as `x.md`). Showing the path relative to the scanned root would point to the right file directly.

- **minor** (`tests/test_docs_sequences.py:67`) The fixture checks only the problem count for ignored arrows

  The return arrow, self-call and actor arrow are covered only by `len(problems) == 1`. That holds today, but the test does not check that the one problem is not, for example, the self-call. An actor *target* (`A->>U`) is also never tested, only an actor source.

- **blocking** Definition of done not met: The documentation the change affects is updated (C25).

  1-context.md, 2-containers.md, the README (sequences hand-written and checked, with the test named) and ADR 0039 are updated, and 3-components.md has 5 sequenceDiagram blocks. But the new `start --shadow` sequence does not describe the code: it skips flow/replay/review_session, which ShadowRun inherits from _TicketRun. The report sequence also puts the tracker read in `report` when `measures` does it.

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

  tests/test_docs_sequences.py adds test_c25_sequences_report_missing_import (a tmp_path fixture in which `B->>C` without an import is reported with its file and arrow, and the return, self-call and actor arrows are not) and test_c25_sequences_repository_passes. Both fail without the new check code, and `-k c25_sequences` selects 2 tests. The test is weak on the shadow sequence, which passes on type-only imports (see the findings).

- **not met**: The documentation the change affects is updated (C25).

  1-context.md, 2-containers.md, the README (sequences hand-written and checked, with the test named) and ADR 0039 are updated, and 3-components.md has 5 sequenceDiagram blocks. But the new `start --shadow` sequence does not describe the code: it skips flow/replay/review_session, which ShadowRun inherits from _TicketRun. The report sequence also puts the tracker read in `report` when `measures` does it.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  The ticket fixed the rules of the check, and ADR 0039 is amended with them (label prefix = module, actors ignored, solid `->>` arrows only, type-only edges count, return arrows and self-calls skipped). No other open choice is visible in the diff.

## Proposed learnings (not decided)

- An import-based check on sequence diagrams cannot catch a diagram that draws a call over an import used only for types or constants. Check new diagrams against the actual call path (subclassing, delegation) and don't stop at a green check.
- `ShadowRun` subclasses `flow._TicketRun`: any shadow-mode diagram or doc should go through the same flow/replay/review_session path as `start`.
- Hand-written Mermaid checks should accept or reject every arrow form (`->>+`, `-)`, `-x`), not skip unknown forms silently.
