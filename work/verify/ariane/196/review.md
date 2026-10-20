# Review 0

- Reviewed commit: `12ce7eb6d964e6e2df32b1692d8ba423d13bfc63`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/review_escapes.py:109`) An update erases escapes attributed to an earlier go

  Metrics.resume preserves earlier reviewer sessions, but escape detection evaluates only the last review and its timestamp. Reproduced without filesystem writes: an initial go followed by human changes requested reports one escape; appending a later update go makes that escape disappear, including from the original model pair. A stopped update also excludes the earlier delivered go entirely through _delivered_go. These are supported start/update paths on the same PR. Evaluate each delivered go against subsequent events and preserve its model attribution before deduplicating tickets.

- **blocking** (`src/ariane/update.py:293`) Unresolved merge stops never record a category

  The sequence is: git merge writes the conflicted index and working tree; git merge --abort fails or leaves changes; _abort raises Unresolved; _left_unresolved emits run.stopped, kills survivors and returns without writing metrics. The previous delivered metrics remain, so report counts no merge stop. Interruptions with a pending merge take the same path. This violates the requirement that every update stop record its category. Preserve the unresolved tree and index, but save categorized metrics outside the repository. Existing abort-failure tests cover this path without asserting categorized metrics; the new update tests cover only successful aborts.

- **blocking** (`src/ariane/flow.py:548`) Delivery guard refusals are categorized as infrastructure failures

  Delivery._require_replayed rejects a head changed outside the ticket records, and Delivery._last_guard rejects push URL rewrites. Both raise PullRequestRefused, which this handler converts to Stop with the default infra category. update.py:428 does the same. Consequently tree and push guard failures are counted as infra rather than the required guard category. The sequence is delivery status/record writes and commit, guard refusal before push, then stop journal, metrics, status and record commit. Carry a category through PullRequestRefused so these guard failures remain distinguishable from tracker failures opening a PR.

- **blocking** Definition of done not met: The change is covered by tests that fail without it.

  New tests exercise escapes, grouping, thresholds and several stop categories, but miss earlier escapes surviving updates, unresolved merge categories and delivery guard categories. The supplied replay reports passing tests; filesystem-writing tests were not rerun under the read-only restriction. A read-only in-memory reproduction confirmed the escape regression.

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

  New tests exercise escapes, grouping, thresholds and several stop categories, but miss earlier escapes surviving updates, unresolved merge categories and delivery guard categories. The supplied replay reports passing tests; filesystem-writing tests were not rerun under the read-only restriction. A read-only in-memory reproduction confirmed the escape regression.

- met: The documentation the change affects is updated (C25).

  README, benchmark, affected module documentation and architecture diagrams were updated. Independently ran scripts/generate_docs.py --check with bytecode writes disabled; it passed, including the unchanged generated CLI reference and log catalogue.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0058 records escape semantics, categories, grouping, thresholds, tracker reads, timestamps and refused-attempt storage. Its last-review-only decision nevertheless misses the supported update sequence described in the blocking finding.

## Proposed learnings (not decided)

- Proposed: test measurement history across updates; a later successful review must not erase an earlier observed escape.
- Proposed: audit exception conversion and early-return paths when adding failure categories, including paths that must preserve an unresolved working tree.

## Run

Slot 0 (`ARIANE_SLOT=0` for the setup, the checks and the reviewer, ADR 0050).
