# Review 0

- Reviewed commit: `d69b3d2f06199720398c6c5e6c70cc6c4e625fa9`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/ticket.py:98`) Loading existing records silently discards directories that restore then deletes

  load() retains only immediate regular files, but restore() recursively removes every entry absent from that snapshot. A clean delivered tree can contain committed work/7/attachments/evidence.md (explicitly permitted by _only_records_beyond), or ignored local attachments. The sequence is: load omits attachments; merge, replay and review run; push_update calls _commit_record; restore recursively deletes attachments; git.commit stages the deletion; _require_replayed permits it because it is under work/7/; the deletion is pushed. A recorded failure also invokes the destructive restore. Ignored contents are lost without any Git recovery. This remains blocking under the proportionality rule because it loses data. A read-only mocked execution confirmed that an existing directory omitted by load is subsequently passed to _remove. Preserve existing contents recursively without following links, or refuse unsupported entries before merging; add regression coverage for tracked and ignored nested contents.

- **minor** (`src/ariane/update.py:93`) Concurrent Linux runs do not recognize update registrations

  The update registers its process with runs.registered, but runs._started_as only accepts a command line containing start <number>. During concurrent start A and update B, B registers and writes its merge commit to ariane/B; A's watcher rejects B as nongenuine, so A's next guard treats B's legitimate branch movement as unauthorized and stops A. Two concurrent updates have the same problem. Extend process recognition to the new command while preserving the existing identity checks, and cover this with separate-process tests. Classified minor because simultaneous update execution is not an explicit acceptance criterion here; this is distinct from the accepted registry-spoofing residual.

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

  tests/test_c11_update.py adds substantive coverage for merging, replay, review, statuses, refusals, conflicts, metrics and remote lease races; the base lacks the imported update module and command. Ariane reports the full checks passing. I did not rerun filesystem-writing tests in this read-only review. Missing coverage includes record-directory preservation and concurrent command recognition. Side-effect audit: command logging and lock/slot files precede eligibility checks; the up-to-date path performs no ticket-record or Git fetch writes. An update then fetches objects/tracking refs/FETCH_HEAD, registers the run, merges into the index/tree/history, writes journal and metrics, creates replay trees and any setup/cache outputs, removes those trees, writes check records, creates/removes the reviewer tree and writes review/session records. Success writes delivery metrics and pushing status, restores and commits records, runs the final guard, performs the leased push, journals the push, publishes statuses, then commits delivered status locally. Red checks/no-go write and commit stop records without pushing. Conflict handling aborts before ticket-record writes; failed abort or unresolved interruption leaves merge state intact. Registry cleanup writes its ended record and removes the live entry. The destructive restore identified above occurs on both success and recorded-stop paths.

- met: The documentation the change affects is updated (C25).

  README includes PowerShell and bash usage. The new update module document, affected module documents, C4 views, CLI reference and log catalogue are updated. The supplied docs-reference check passed.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0033's amendment records review numbering, refusals, the atomic leased fast-forward push, no-op logging, incoming-file check selection, residual provenance, metrics continuation and unresolved-merge handling. The destructive record restoration is an implementation defect rather than an acceptable additional design choice.

## Proposed learnings (not decided)

- Proposed: test load-and-restore round trips against all existing content, including nested and ignored files, before using restoration on resumed work.
- Proposed: when adding a registered command, test that concurrent processes recognize its identity and tolerate its authorized branch writes.

## Run

Slot 0 (`ARIANE_SLOT=0` for the setup, the checks and the reviewer, ADR 0050).
