# Review 0

- Reviewed commit: `09e38fb544cf6625fc6bb3e42f14127b9621d75c`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/replay.py:200`) Remote changes can be undone by a later check before verification

  With sequential checks, check A can push a tag, then check B can delete it. The new order is: create A's worktree; run setup and A (remote tag created); verify locally and write the successful guard journal entry; remove A's worktree; create B's worktree; run setup and B (remote tag deleted); verify locally and journal success; remove B's worktree; finally compare remote refs. That comparison sees the original state and permits review and delivery. Previously A's remote change stopped replay before B ran. The added remote-tampering test places the push in the last check, so it misses this regression. Although the ticket permits consolidating remote listings, it explicitly requires preserving the existing tampering detection; this implementation does not.

- **blocking** (`docs/adr/0053-fewer-git-processes-per-run.md:128`) Required performance evidence is incomplete

  The ADR explicitly leaves the Windows result pending and acknowledges that the 30–33% process reduction may miss the required 40% duration reduction. No recorded PR CI result establishes that the 30 slowest Windows tests total at most 60% of ADR 0049's baseline. The requested Linux timings by phase are also absent: the phase table records counts, while timings are aggregate suite or example-test durations. Record the phase timings and Windows baseline/result sums with CI provenance, and meet the target before declaring this ticket complete.

- **blocking** (`docs/architecture/modules/verify.md:27`) Changed verify module lacks its required documentation update

  src/ariane/verify.py now uses git.detached_head for its replay/reviewer head check, but its module document is unchanged. The supplied documentation rule explicitly requires updating the module document of every touched module. Describe the consolidated head check and its ADR 0053 relationship here; the updates to git.md and replay.md do not satisfy that requirement.

- **blocking** Definition of done not met: The documentation the change affects is updated (C25).

  The component view and flow, git, replay and runs module documents were updated, but the touched verify module's document was not.

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

  The four whole-run process-bound tests impose limits below the recorded pre-change counts, and the snapshot and commit tests require the new three-process implementations. Ariane reports the suite passing. I did not rerun tests because this review permits no filesystem writes. The remote restoration case remains uncovered.

- **not met**: The documentation the change affects is updated (C25).

  The component view and flow, git, replay and runs module documents were updated, but the touched verify module's document was not.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0053 records snapshot consolidation, deferred configuration parsing, ancestry caching, detached-head reads, remote-listing placement and commit optimization, including alternatives. Its required performance evidence remains incomplete, as separately reported.

## Proposed learnings (not decided)

- When consolidating security checks, test a mutation followed by restoration across the boundaries that previously triggered verification.
- Process-count reductions do not establish a platform-specific wall-time acceptance target.
