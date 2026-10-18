# Review 2

- Reviewed commit: `8aaad267593e205221de0b0492b646543e81b190`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/runs.py:184`) Agent-writable history can authorize unregistered branch changes

  The guard trusts ended.jsonl without establishing that Ariane wrote its entries. An implementer can append {"number":8,"ended":"9999"}, create or move ariane/8 and add its allowed configuration keys. After the session, during() returns 8 and foreign_changes() discards those changes although no second run existed. A read-only, mocked probe confirmed that this fabricated record authorizes ticket 8. Protect or authenticate the authorization source and add a regression test for registry tampering.

- **blocking** (`src/ariane/runs.py:198`) The merge-key allowance exceeds the decided spec

  The ticket permits only merge=refs/heads/ariane/<m>, but this also permits merge=refs/heads/<base>. A mocked snapshot comparison confirmed that adding branch.ariane/8.merge=refs/heads/main is silently accepted. The ADR explains Git's preparation behavior, but that does not satisfy the ticket's explicit exact-value restriction. Align preparation and filtering with the decided spec, or obtain an explicit specification change.

- **blocking** (`src/ariane/runs.py:133`) Cleanup removes registration even when publishing history fails

  The intended write order is append the ended record, then remove the live entry. Here an append failure is suppressed and _release still removes the entry. Interleaving: run B creates its branch during A's session; B's history append fails; B removes its registration; A reads the registry and rejects B's legitimate changes. A mocked failure probe confirmed release occurs after the failed append. Preserve the evidence or explicitly handle publication failure before removing the entry, and test this failure path.

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

  The new test_c11_parallel_guard suite covers registered and unregistered branches, forbidden keys, hooks, cleanup, stale entries and concurrent registration. The registered-branch success case exercises behavior rejected by the previous guard. Ariane reports green tests; the failure paths identified above remain uncovered.

- met: The documentation the change affects is updated (C25).

  README, the component sequence, module documentation for flow/git/runs/stop, and ADR 0017 are updated. No log event template was changed.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0017 records the registry format, OS locking, atomic registration, ended-run history and snapshot ordering. Its additional merge-value allowance is documented but conflicts with an explicit requirement rather than resolving an open choice.

## Proposed learnings (not decided)

- Proposed: authorization records used to relax a security guard must be protected against the untrusted code that guard checks.
- Proposed: test publication failures between ordered writes, not only successful concurrent interleavings.
- Proposed: an ADR can resolve an open design choice but cannot silently broaden an exact acceptance requirement.
