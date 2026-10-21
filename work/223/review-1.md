# Review 1

- Reviewed commit: `4b06b1744fde36a7b4376ad6363804721f27eb4b`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/next_start.py:135`) Relabeling can approve issue content that was never analyzed

  The handoff lock protects local registrations, not GitHub edits. Interleaving: propose() reads an issue with no conflicting paths or unmet dependencies; another request edits its body to add either; _launch then removes and adds the ready label and launches start. The child reads the edited issue, whose edit now predates the fresh maintainer label, so the existing issue gate accepts it. Nothing binds the child's issue to the version analyzed by next. The relevant write order is reservation temporary file → reservation replacement → start-intent append → DELETE label → POST label → output-file creation/append and process launch → launched-reservation replacement → child registration → start-record append → reservation removal/update → technical log. The missing revision check allows the relabel and execution to bless unanalyzed content, breaking the issue-gate security property and making the shared-file/dependency checks pass wrongly. Bind execution to the analyzed issue revision and test an edit between analysis and relabeling.

- **blocking** (`src/ariane/next_ticket.py:98`) Ordinary path notation bypasses shared-file detection

  Read-only execution confirmed that expected_paths('Edit [src/ariane/cli.py](src/ariane/cli.py).', ...) and expected_paths('Edit `src/ariane/cli.py:65`.', ...) both return no paths. It also preserves src/ariane/./cli.py literally, which shared() considers disjoint from src/ariane/cli.py. Consequently a running ticket changing cli.py does not block a candidate explicitly naming that same file in these forms. Extract Markdown paths and file references, and normalize equivalent relative paths before comparing them. Add regression tests asserting that these candidates are blocked and the shared path is named. This makes the safety check pass wrongly, rather than merely reducing the quality of the displayed explanation.

- **blocking** (`src/ariane/next_start.py:137`) A crash after spawning can lose the live child's reservation

  The initial reservation names the parent PID. The process is spawned at line 137, and only afterward does line 150 replace that reservation with the child PID. If the parent dies between these writes, the child survives because it is detached, but the reservation still names the dead parent. After 60 seconds, Reservation.pending() returns false if the child has not registered yet, and reconcile() appends 'start reconciled' and deletes the reservation. A new next invocation can then record and launch a conflicting ticket; the original child can subsequently finish its tracker reads and register using ARIANE_NEXT_LAUNCH, bypassing the handoff lock. Slow tracker requests can exceed this interval. The same gap occurs when post-launch reservation writes fail. Preserve an authoritative child claim across this crash window, or require a delayed child to validate its reservation and safety before registering. Test parent death between spawn and reservation replacement with a child that registers after the grace period.

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

  The three new test files contain 29 test_c23_next_* tests covering queue order, dependencies, overlaps, slots, quota, confirmation, records, concurrency and launch behavior. They depend on APIs absent before this change. Ariane reports the test replay passed; I did not rerun filesystem-writing tests. The findings identify missing regression cases.

- met: The documentation the change affects is updated (C25).

  The README, new module pages, affected module documentation, container/component views, configuration example, generated CLI/schema references and log catalogue are updated. Some documented safety guarantees need correction through the blocking fixes.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0059 records queue ordering, dependency syntax, path extraction and glob semantics, blockers, confirmation, locking, reservations, recovery and detached execution. The findings concern correctness of those mechanisms, not missing design records.

## Proposed learnings (not decided)

- Proposed: bind authorization and execution to the exact issue revision used for safety analysis.
- Proposed: test crash recovery at the boundary between process creation and durable child identification.
- Proposed: test path-conflict detection with Markdown links, line references and equivalent normalized paths.
