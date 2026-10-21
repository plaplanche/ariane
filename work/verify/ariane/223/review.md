# Review 0

- Reviewed commit: `dde98418743568725f80c2f715cfedad2a77eca3`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/next_start.py:149`) The fresh ready label can authorize an unanalysed revision before validation

  The write order is: write reservation, append start intent, remove ready label, add ready label, then check the revision and possibly remove the label and record refusal. An editor can change the body between the first revision check and add_labels. A concurrent manual `ariane start N` can then read that edited body with the fresh maintainer label and pass the issue gate: flow.start reads the issue at line 65, before acquiring the handoff lock through runs.registered. Even if next subsequently detects the edit, removes the label, deletes the reservation and releases the lock, the manual start retains its accepted Issue and proceeds to registry writes, branch/worktree preparation and agent execution without revalidation. This breaks the issue-gate security property. A read-only, mocked reproduction confirmed that the manual read retains the edited body while next reports refusal. The existing edit tests check only next's own launch. Serialize manual issue acceptance with the handoff, or revalidate the accepted revision after acquiring it; add a regression covering this interleaving. Also cover failure of the post-relabel read, which currently leaves the fresh label in place.

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

  The four new test_c23_next files cover queue ordering, dependencies, shared paths, slots, quota, confirmation, detached launch, records and handoff recovery. Their new APIs are absent before the change. Ariane reports the full suite passing. The concurrent manual-read security case identified above is missing; filesystem-writing tests were not rerun in this read-only review.

- met: The documentation the change affects is updated (C25).

  README, container/component views, affected module documentation, new module pages, example configuration, generated CLI/schema references and log catalogue are updated. The handoff's claimed revision guarantee needs correction alongside the blocking fix.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0059 records queue ordering, dependency syntax, path inference, overlap rules, confirmation comparison, detached execution, reservations, recovery and revision checks.

## Proposed learnings (not decided)

- Proposed: A lock protecting registration must also protect earlier authorization reads whose results survive until registration.
- Proposed: Test externally visible authorization writes with concurrent consumers and failures before compensating cleanup.

## Diff given to the reviewer

The diff (201,859 characters) was cut at 200,000; the reviewer was given every changed path and told to read these in the tree:
- `tests/test_c23_next_start.py`
- `tests/test_github.py`

## Run

Slot 0 (`ARIANE_SLOT=0` for the setup, the checks and the reviewer, ADR 0050).
