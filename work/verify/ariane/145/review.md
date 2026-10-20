# Review 0

- Reviewed commit: `22273bb12679db5dd15bcb7ed59ea7315b656413`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/update.py:354`) Replay selection excludes changes imported from the base

  Passing the fetched base as start_commit makes replay.replay select checks from base..merged. Files imported unchanged from that base disappear from this diff. For example, a documentation-only ticket updated with a base change to src/app.py skips a blocking check scoped to src/**, even if that check now fails. Imported lock-file changes likewise cannot trigger check_all_paths. The sequence is merge written → affected check skipped and treated as passing → review → records committed → leased push → success status published for the skipped check. Thus the push can happen without the blocking validation required for the update. Select checks using changes that include the incoming base changes, or run every check for updates; keep the requested review diff separate. Add a regression with a scoped blocking check broken by an incoming base change. The current red-check test uses an always-selected check.

- **minor** (`src/ariane/update.py:277`) Merge-hook documentation disagrees with the actual invocation

  The docstring and module documentation say commit hooks may run, but the merge calls git.git, which always supplies core.hooksPath=os.devnull. The untrusted environment does not override that command-line setting. Clarify the intended hook policy and make the implementation, ADR and documentation agree; add coverage if hooks are intended to execute.

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

  The new test module contains 18 test functions, with additional parametrized cases, covering delivery, refusals, conflicts, interruption, remote races, metrics and CLI wiring. These depend on the new update implementation. The supplied replay reports passing checks; I did not execute tests because they create files. Coverage misses scoped checks affected by incoming base changes. Side-effect audit: CLI logging and lock/slot files precede refusals; up-to-date returns before fetch or ticket-record writes. Otherwise fetch writes git metadata, registration writes run metadata, merge writes the index/tree/commit, journal and metrics are written, replay creates/setup/checks/removes clean trees and may populate caches, review creates/removes its tree and writes its records, delivery commits records, checks the remote, performs the leased push, journals it, publishes statuses, then commits local delivery records. Conflict handling aborts before recording; failed abort or unresolved interruption avoids record commits. Red/no-go paths commit stop records without pushing. Registry cleanup records completion. Git commands and journal warnings also emit technical logs. The explicit push lease closes the last-read/push race.

- met: The documentation the change affects is updated (C25).

  README includes PowerShell and bash usage; the CLI reference, log catalogue, context/container/component views, new update module page and affected module pages were updated. The supplied documentation-reference check passed. The hook-policy discrepancy is noted as a minor finding.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0033's amendment records the second push and atomic lease, per-commit divergence checks, no-fetch up-to-date handling, review numbering, resumed metrics, unresolved-merge preservation and recovery after a stopped update. The replay-selection finding concerns correctness of the required validation.

## Proposed learnings (not decided)

- Proposed: distinguish the diff used to review a ticket from the changes used to select validation after integrating another branch.
- Proposed: test update replay with path-scoped checks and incoming lock-file changes, not only always-run checks.
- Proposed: verify wrapper-added git options when documenting whether hooks execute.

## Run

Slot 1 (`ARIANE_SLOT=1` for the setup, the checks and the reviewer, ADR 0050).
