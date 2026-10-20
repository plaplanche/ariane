# Review 2

- Reviewed commit: `5a0e644f98fef432c0a551fc11cb65da79cde29e`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/full_replay.py:145`) A failing full replay can publish a success status

  Publication uses only the escape list to determine success. If an advisory check fails in both the selective round and the full replay, while another check was skipped, sampling is eligible but escapes() excludes the existing failure. The subsequent writes are metrics, full-replay.md containing the failure, a 'Full replay passed' journal entry, then a success ariane/full-replay status. A read-only in-memory probe reproduced this. This makes a check pass wrongly: absence of new escapes does not mean the full replay passed. Determine the full-replay verdict from all full results, separately from escape classification, and add coverage for an already-failing advisory check.

- **blocking** (`src/ariane/measures.py:154`) Stopped replays silently erase detected escapes from the report

  full_replay() excludes every stopped replay, including those with verified escapes already recorded and published. With one passing completed replay and one replay that detects an escape before a later setup fails, a read-only probe produced '1 full replays, 0 escapes, escape rate 0/1 (0.0%)' and no warning. The ticket requires reporting full replays run, escapes and their rate; this hides precisely the failures that measurement is intended to expose. ADR 0056 documents the exclusion, but it is not an owner-accepted residual and contradicts that requirement. Preserve detected escapes and report interrupted samples explicitly; incomplete durations can be excluded separately from the time-saving comparison. Update the test that currently expects these escapes to disappear.

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

  The new test module covers sampling, post-delivery execution, escape records and publication, unchanged pushed commits and review results, interruptions, configuration and reporting. These assertions depend on the new behavior. The two cases identified above need corrected regression coverage. Ariane supplied passing check results; filesystem-writing integration tests were not rerun during this read-only review.

- met: The documentation the change affects is updated (C25).

  README, the example configuration, schema, log catalogue, component sequence and affected module documentation are updated, including the new full_replay module. Documentation also describes the problematic behaviors identified in the findings and must change with their fixes.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  The ADR 0056 amendment records deterministic sampling, post-delivery execution, local-only records, reporting discovery, status naming, interruption handling and measurement semantics. Recording a choice does not resolve the requirement conflicts identified above.

## Proposed learnings (not decided)

- Proposed: Test full-replay success independently from escape detection; no new failure is not equivalent to all checks passing.
- Proposed: Keep observed failures visible when later work is interrupted, and distinguish incomplete timing samples from failure counts.
