# Review 0

- Reviewed commit: `6a04bd7db970eeaa6af2d14caa1181100d35e19f`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`docs/adr/0049-template-project-and-windows-shards.md:262`) The required Windows performance result is still pending

  The latest recorded unsharded Windows tests step is 905 seconds, above the required 570-second limit. Both shard measurements, the final Linux/macOS measurements, and the sharded run URL remain pending. Two shards cannot be assumed to meet the target. Record the pull request's successful sharded CI run and each Windows shard's Tests duration; use three shards if the measured result requires it.

- **blocking** (`docs/adr/0049-template-project-and-windows-shards.md:74`) The required Windows baseline and measurement-driven selection are missing

  The ADR explicitly says the Windows before-change list was not taken, and lines 99–105 select the five optimizations provisionally from Linux process counts. This does not satisfy the decided specification to record the 30 slowest Windows tests before the change and choose the next five avoidable setups from that measurement. The abbreviated after-change test-body list cannot establish the ranking of setups already removed. Measure the base revision on Windows with --durations=30, record identifiable tests and timings, and reconcile the five selections against that evidence.

- **minor** (`docs/adr/0049-template-project-and-windows-shards.md:317`) The consequences describe serial CI jobs that were removed

  This paragraph says CI runs the whole suite serially on all three systems, whereas the checked-in workflow has no serial job and lines 153–158 describe its removal. Describe the serial runs as completed one-time validation so the ADR accurately explains the final workflow.

- **blocking** Definition of done not met: The documentation the change affects is updated (C25).

  README documents templates, shards and duration refreshes; no src module changed, so architecture updates are unnecessary. However, ADR 0049 lacks required baseline and final performance evidence and contains an obsolete statement about serial CI jobs.

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

  The new template tests cover independent objects and refs, isolated pushes, origin rewriting, preserved fixture contents, one template per session, and copying without subprocesses. Rebuilding the fixture per test violates the latter two checks. The shard test checks disjoint and complete collection. Ariane reports the suite green; I did not rerun tests because this review permits no writes. Side-effect inspection found template creation proceeds through init, clone, checkout, file writes, add, commit and push before use; each project then copies the remote, copies the checkout, validates the URL line and rewrites only its own config before returning. The fast-import helper writes objects and updates the target branch before the existing guard assertions run. No shared-template write or new interleaving defect was identified.

- **not met**: The documentation the change affects is updated (C25).

  README documents templates, shards and duration refreshes; no src module changed, so architecture updates are unnecessary. However, ADR 0049 lacks required baseline and final performance evidence and contains an obsolete statement about serial CI jobs.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0049 records direct config rewriting, per-worker isolation, fast-import for branch setup, pytest-split with least_duration, stored durations, shard thresholds, alternatives and required check names. The missing measurements are acceptance gaps rather than unrecorded design choices.

## Proposed learnings (not decided)

- Capture platform-specific baselines before optimization; post-change timings cannot reconstruct removed setup costs.
- Passing correctness checks and estimating shard balance do not establish a measured performance acceptance criterion.
