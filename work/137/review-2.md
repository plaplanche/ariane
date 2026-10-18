# Review 2

- Reviewed commit: `1a31dbce37a90826d9c74b48f3fed66b0879ea0e`
- Reviewer model: gpt-6-astra
- Verdict: **go**

## Findings

- **minor** (`tests/test_c10_small_review.py:51`) Threshold equality and switching after a fix round lack regression coverage

  The tests exercise a two-line diff against thresholds of 10 and 1, but never exactly 2 or a fix round that crosses the threshold. The implementation correctly uses <= and recomputes each round, but changing either behavior could escape these tests. Add an equality case and a fake-runtime fix round asserting the updated model, prompt and changed_lines.

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

  Fourteen named test functions cover selection, configuration rejection, exclusions, verify, credentials and records; their new behavior assertions fail without this implementation. Ariane reports all checks passing. Tests were inspected, not rerun because this review permits no writes. Order traced: create reviewer tree; read diff and count; select settings; create temporary session directory; journal instructions and start; call runtime; record metrics and stop; check guards; validate answer; record verdict; remove temporary trees. Invalid-answer retries repeat the session and accounting after guard checks. Verify additionally checks branch state before writing and committing final records. No ordering defect introduced by this change was found.

- met: The documentation the change affects is updated (C25).

  README, all touched modules' architecture documents, the commented configuration example and generated configuration schema describe the new settings, selection, credentials and records. Ariane reports the generated-reference check passing.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0046 records the threshold mechanism and rationale, model independence, inherited settings, idle-limit handling, provider-specific credentials, cap diagnostics and per-round records.

## Proposed learnings (not decided)

- Proposed: Test size-based routing at the exact threshold and across a fix round that changes the routing decision.
