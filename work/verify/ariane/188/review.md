# Review 0

- Reviewed commit: `3cb8c046ea9badb62a034abb69531d8f09403c33`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/process.py:189`) Protected groups are forgotten when a baseline process disappears

  The protected set is rebuilt from each scan rather than retained. A mocked execution reproduced this interleaving: scan 1 finds a process in before and a new descendant sharing its group/session; only the new pid receives SIGSTOP. The baseline process then exits and is reaped by its owner. Scan 2 forgets its group/session and sends them SIGSTOP; scan 3 sends them SIGKILL. This violates the requirement that groups/sessions belonging to before are never signalled and can affect other members. Preserve the baseline group/session exclusions across scans and add a regression with changing tables.

- **blocking** (`src/ariane/process.py:202`) Empty-scan return bypasses SIGKILL for discovered groups

  The return condition ignores groups awaiting SIGKILL and precedes the deadline check. Replaying the new zombie test's tables produced this complete side-effect sequence: reap zombie, SIGSTOP its group and session, then return {} on the empty scan. Neither group receives SIGKILL. Thus an incomplete subsequent /proc scan can leave a stopped survivor behind, and even an expired deadline cannot trigger the promised final kill. Finish the group-kill phase before allowing this return; extend the zombie regression to assert SIGKILL as well as SIGSTOP.

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

  Four new c10_survivor_groups tests cover group protection, zombie discovery, deadline killing, and a 20-iteration forking scenario. Group-signal assertions distinguish the previous implementation. Ariane reports the suite passing; the two changing-snapshot cases identified here remain uncovered.

- met: The documentation the change affects is updated (C25).

  The process module documentation and ADR 0031 describe group/session cleanup and the repeated-setsid residual. Log declarations and message text are unchanged, so no log catalogue regeneration is needed.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0031's #188 amendment records the cleanup strategy, exclusions, zombie ordering, deadline behavior, counting, and residual limitation. The findings are implementation deviations from those decisions.

## Proposed learnings (not decided)

- Proposed: test process cleanup with changing scan snapshots, including disappearance of protected processes.
- Proposed: assert the complete stop-to-kill sequence; observing SIGSTOP alone does not prove cleanup completes.
