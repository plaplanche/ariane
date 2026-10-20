# Review 0

- Reviewed commit: `73b51519e4bf2d0bbb2a1164cad14b04ced14a88`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered go)

## Findings

- **minor** (`src/ariane/update.py:94`) Concurrent runs do not recognize update processes on Linux

  The update registers itself, but runs._started_as accepts only command lines containing `start <number>`. Interleaving: another ticket snapshots the repository; update registers and writes its merge commit; the other ticket checks its guard. The update is excluded from genuine runs, so its branch movement stops the other ticket as an unauthorized change. Two concurrent updates can likewise stop each other. Extend process recognition to update and test this interaction. Minor because concurrent updates are not an acceptance criterion and this fails closed.

- **minor** (`src/ariane/metrics.py:44`) Malformed-metrics recovery policy is missing from ADR 0033

  resume silently starts measurements empty when existing JSON cannot be parsed or converted. The next metrics write replaces that file. The module documentation describes this fallback, but ADR 0033 only promises that earlier measurements are continued. Record the fallback decision and its consequences in the ADR, with a test establishing the intended behavior.

- **blocking** Definition of done not met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0033 records the lease, numbering, record preservation, check selection, risk calculation and interrupted-merge behavior, but omits the malformed-metrics fallback identified above.

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

  The three new test modules cover the command, merge parents, replay, review numbering, statuses, refusals, conflicts, interrupted aborts, remote races, metrics continuation and selective checks. They depend on the new implementation. Ariane reports passing checks; I did not rerun tests because this review permits only reads. Side-effect trace: CLI logging and lock files precede refusals; fetch writes objects, FETCH_HEAD and tracking metadata when needed; registration writes registry records; merge writes index, tree and commit; journal/status/metrics writes follow; replay and review create and remove separate trees and write their records; delivery commits records, checks guards, performs the leased push, writes the pushed journal entry, publishes statuses, then commits delivered status locally. Conflict handling aborts and verifies restoration before writing stop records; unresolved merges bypass record commits. Red checks and no-go reviews record a local stop without pushing. The known up-to-date path avoids fetch, merge and ticket-record writes.

- met: The documentation the change affects is updated (C25).

  README includes PowerShell and bash usage. CLI reference, log catalogue, context/container/component views, touched-module documentation and the new update module documentation are updated.

- **not met**: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0033 records the lease, numbering, record preservation, check selection, risk calculation and interrupted-merge behavior, but omits the malformed-metrics fallback identified above.

## Proposed learnings (not decided)

- When adding an orchestrator command, update process-authentication rules as well as run registration.
- Keep remote-head comparison atomic with the push, and verify merge restoration before any record commit can reset the index.

## Run

Slot 0 (`ARIANE_SLOT=0` for the setup, the checks and the reviewer, ADR 0050).
