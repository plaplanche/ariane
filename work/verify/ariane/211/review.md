# Review 0

- Reviewed commit: `98006d96ee5c7d2ab7e149a66ec22c0254e2e0cf`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/claude_code.py:203`) Implementer quota stops cannot reach the resume path

  Claude Code is the only permitted implementer runtime, but its result parser never returns QUOTA: only success, budget and turns have mappings, and every other failure becomes ERROR. A runtime message reporting its usage limit therefore records error, supplies no reset_at and causes --resume to refuse. This misses the explicitly required implementer and fix-session quota cases. A read-only parser probe with an error_during_execution result containing a usage-limit message produced reason=error, reset_at=None and resumable=False. Add runtime quota classification and reset-time extraction, with fixtures and an implementer/fix-session integration test; the current quota tests exercise Codex or fabricated SessionResults.

- **minor** (`src/ariane/resume.py:266`) Resumed fix rounds retain their count but lose their findings

  enter restores metrics.rounds but leaves run.reviews empty, after restoring work/ to the base. The initial resumed implementer also receives fix_round=0 and no findings. Consequently, a fix-session interruption resumes without its full review feedback, and subsequent reviewers receive no earlier-findings context. Four truncated journal entries are not a reliable substitute for that feedback. Consider carrying the prior review context separately from the new run's records, and test a quota or limit interruption after a no-go.

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

  test_c5_resume.py adds regression tests for saved work, raised limits, prompts, refusals, repeated resumes and reviewer quotas; these depend on functionality absent before this change. Ariane reports passing checks. I did not rerun filesystem-writing tests in this read-only review. Coverage misses actual implementer quota classification. Side-effect order inspected: lock and slot acquisition, registry writes, eligibility/reset-time check, fetch, saved-work objects, atomic creation of the kept ref, tree removal and branch deletion, new branch/tree creation, reset to kept head, work/ restoration and commit, setup, new records, agent session when applicable, verification, work commit, replay and review, then delivery. Eligibility precedes destructive cleanup, and the kept ref precedes removal.

- met: The documentation the change affects is updated (C25).

  README, example configuration, requested module documentation, new resume module documentation, schema and CLI references, and log catalogue are updated. The reported docs-reference check passed. The documented implementer quota behavior remains unimplemented as noted above.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0062 records branch continuation, record resetting, prompt contents, factor and caps, turn-limit fallback, repeated-resume policy, quota handling, reset-time parsing and continued fix-round counts.

## Proposed learnings (not decided)

- Proposed: Test resumable stop reasons through each supported runtime's parser, not only through fabricated SessionResults.
- Proposed: When continuing an interrupted fix round, consider its review feedback alongside its round count.

## Run

Slot 1 (`ARIANE_SLOT=1` for the setup, the checks and the reviewer, ADR 0050).
