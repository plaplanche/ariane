# Review 0

- Reviewed commit: `5f59be3431bb477877efe6f8611baefacb16472b`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/resume.py:264`) Resuming discards earlier blocking findings while continuing fix rounds

  After a no-go followed by a fix-session limit or reviewer quota, enter restores metrics.rounds but leaves run.reviews empty. The subsequent reviewer receives no earlier findings, and review_history.validate accepts a go without answering them. This makes the existing review check pass wrongly. The write order is: save outstanding work, create the kept ref, remove old trees and branch, create the new branch, reset to the kept head, restore and commit work/ from the base, then write new records and replay/review. Although the kept branch preserves the old reviews, nothing reloads them before the review gate. Restore the prior review history as well as the round count, and test a resume after a blocking review with an answer that omits the earlier findings.

- **blocking** (`src/ariane/flow.py:419`) Implementer quota stops omit the reset time from the stop message

  The ticket explicitly requires a quota stop message to name the runtime's reset time. This path builds the reason from result.stop_text(), which returns only 'quota', and supplies a generic journal next action, discarding result.next_step and result.reset_at. Thus an implementer or fix-session quota with a known reset time prints --resume without saying when it can run. The reviewer path handles next_step, but this path does not. Include the reset time and add a stop-line assertion for implementer and fix-session quota stops.

- **minor** (`src/ariane/claude_code.py:240`) Quota classification drops usage already reported by Claude Code

  The new early return preserves total_cost_usd but discards all four usage counters, num_turns and permission denials from the structured result. A read-only reproduction with populated usage and num_turns returned None for every token counter and turns. Build the normal SessionResult first, then replace its stop classification, reset time and next action so quota metrics retain the runtime's reported measurements.

## Definition of done

- met: check lint passes

  Replayed by Ariane: exit 0.

- met: check format passes

  Replayed by Ariane: exit 0.

- met: check types passes

  Replayed by Ariane: exit 0.

- met: check types (Windows) passes

  Replayed by Ariane: exit 0.

- met: check tests passes

  Replayed by Ariane: exit 0.

- met: check file length passes

  Replayed by Ariane: exit 0.

- met: The change is covered by tests that fail without it.

  The new test_c5_resume_* tests exercise saved-head ancestry, saved files, raised limits, caps, prompt envelopes, eligibility refusals, repeated-limit refusal and reviewer quota continuation. These depend on APIs and behavior absent from the base. Ariane reports the full suite passing; I did not rerun filesystem-writing integration tests in this read-only review. Prior review-history continuity and implementer reset-time stop messages lack coverage.

- met: The documentation the change affects is updated (C25).

  README, the example configuration, the requested module documentation, the new resume module documentation, generated configuration schema, CLI reference and log catalogue are updated. Ariane reports the documentation-reference check passing.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0062 records saved-head continuation, record cleanup, diff base, prompt contents and truncation, factor and caps, turn-limit fallback, quota reset parsing, round continuation and the once-in-a-row rule. ADR 0043 marks its quota next action superseded.

## Proposed learnings (not decided)

- Proposed: When resuming a gated workflow, restore the evidence consumed by its gates, not just its progress counters.
- Proposed: Test quota handling through each role's final user-visible stop line, including the reset time.
- Proposed: Classifying a runtime result should preserve measurements already present in that result.

## Run

Slot 0 (`ARIANE_SLOT=0` for the setup, the checks and the reviewer, ADR 0050).
