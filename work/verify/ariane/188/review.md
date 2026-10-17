# Review 0

- Reviewed commit: `7d9ef5cbefc5a86be4ce46050619498883116fa5`
- Reviewer model: gpt-6-astra
- Verdict: **go**

## Findings

None.

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

  Five test_c10_survivor_groups_* tests cover 20 consecutive forking runs, baseline and own-group protection, zombie group discovery, deadline SIGKILL, and protection after a baseline process exits. The group-signal assertions require behavior absent from the base implementation. Ariane reports the full test replay passed; tests were not rerun during this read-only review.

- met: The documentation the change affects is updated (C25).

  The process module documentation and ADR 0031 describe group/session cleanup and its residual limitation. No log event or message changed. Audited cleanup side-effect order: read group protection and targets; reap exited children; send group SIGSTOP then new-pid SIGSTOP; on stabilization send group SIGKILL then pid SIGKILL; rescan and reap. The deadline sends group and live-pid SIGKILL before logging survivors_remaining. The empty-scan path kills previously stopped groups before returning. Finally, survivors_killed is logged and the accumulated killed-process record is updated.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0031's #188 amendment records persistent protection of observed baseline groups, handling of empty scans after stopping groups, group-member accounting, deadline behavior, and the residual escape through repeated setsid(). No additional undocumented behavioral choice was identified.

## Proposed learnings (not decided)

- Retain process group and session information before reaping zombies; exited generations can identify a running descendant missed by a scan.
- An empty follow-up scan must not skip SIGKILL for groups previously stopped.
