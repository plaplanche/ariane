# Review 0

- Reviewed commit: `3478a06dd0bb1194c0112203a0fe1c4344e9e8c5`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/process.py:180`) Cleanup can abandon survivors without sending SIGKILL

  The teardown sends SIGSTOP, waits until every survivor reports T/t, and only then sends SIGKILL. If a descendant remains in uninterruptible I/O (D) for five seconds, the deadline branch returns without ever sending SIGKILL. It nevertheless records that descendant as killed. One such descendant also prevents killing the other, already stopped descendants. Subsequent guard cleanup repeats the same sequence and can abandon them again when the ticket exits. A read-only mocked reproduction returned a supposedly killed process with SIGSTOP as the only signal sent. Queue SIGKILL before abandoning cleanup, distinguish remaining processes from confirmed kills, and test this deadline path.

- **minor** (`src/ariane/review.py:242`) Quoted binary filenames are corrupted in the truncation list

  The header fallback assumes unquoted a/path and b/path strings. Git quotes filenames containing non-ASCII bytes or special characters. For a binary file whose header contains "a/\303\251.png" and "b/\303\251.png", a read-only reproduction returned /\303\251.png" as the missing path. The changed-file list remains intact, but the prompt and journal name a nonexistent path. Parse quoted headers and add coverage for binary and mode-only changes with quoted filenames.

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

  The added integrity tests exercise external instruction-file writes, complete changed-file lists and truncation notices, and detached-process cleanup and refusal. These assertions depend on the new behavior. Ariane reports the suite passing; I did not rerun filesystem-writing tests in this read-only review. The cleanup deadline case remains uncovered.

- met: The documentation the change affects is updated (C25).

  README, ADR 0031, the affected architecture modules and the log catalogue are updated. The unchanged shadow document still describes its behavior accurately: its direct code change only relocates the error-description helper. Cleanup's documented guarantee requires the blocking fix.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  The ADR 0031 amendment records runtime-specific instruction coverage, survivor accounting, cleanup deadlines, interrupted-run metrics, and platform residuals. Recording the deadline does not resolve the implementation's failure to send a kill signal.

## Proposed learnings (not decided)

- Proposed: test cleanup deadlines with descendants that never acknowledge SIGSTOP; a signal request is not proof of termination.
- Proposed: test Git path parsing with quoted filenames, binary changes and mode-only changes.
