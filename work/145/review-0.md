# Review 0

- Reviewed commit: `84f747d307daa11de5744aba0dfe501f804435eb`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/update.py:304`) Remote-head validation is not atomic with the push

  The successful path writes the merge, journal and metrics, creates and removes replay/reviewer trees, writes check/review records, commits the pushing status, reads the remote head, then separately calls git.push; afterward it writes the pushed journal entry, external commit statuses and a local delivery-record commit. Between the last remote read and git.push, another actor can delete the remote branch or move it to an ancestor of the proposed head. The ordinary push then succeeds, recreating or advancing that changed branch despite the explicit requirement to push only if it has not moved. The ticket lock cannot exclude external writers. Enforce the expected remote object ID atomically at the remote update while retaining the fast-forward requirement, and test a mutation after the final guard.

- **blocking** (`src/ariane/update.py:172`) Endpoint diff does not enforce records-only extra commits

  The refusal checks only the aggregate tree difference between remote and local. A local commit changing application code followed by its revert produces an empty difference and passes, although both extra commits touch files outside work/<n>/. Those commits subsequently become part of the pushed history. This violates the explicit refusal for extra commits that touch anything beyond the ticket records. An in-memory probe confirmed that an ancestor relationship with an empty endpoint diff is accepted. Inspect the paths touched by every extra commit, including merge commits, and add a change-then-revert regression test.

- **blocking** (`src/ariane/update.py:292`) Delivery refusals escape without recording the stop

  Delivery.push_update can raise PullRequestRefused from _require_replayed or _last_guard, but execute_update catches only Stop, KeyboardInterrupt and FAILURES; PullRequestRefused belongs to none of them. Unlike flow._deliver, this call has no conversion to Stop. For example, a matching push-URL rewrite causes an uncaught exception after metrics have been marked delivered and the pushing records committed. Nothing is pushed, but no stop is recorded and the required one-line outcome is lost. An in-memory probe confirmed the exception escapes without calling _stopped. Convert it to a needs-a-human Stop and test the refusal path.

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

  tests/test_c11_update.py adds integration coverage for the new command, merge, replay, review, push, refusals, conflict, negative outcomes and metrics continuation. These depend on the new implementation. Ariane reports the suite passing; the boundary cases identified above remain uncovered. Integration tests were not rerun in this read-only review.

- met: The documentation the change affects is updated (C25).

  README includes PowerShell and bash usage; the CLI reference, log catalogue, context/container/component views and affected module documentation are updated, including a new update module page.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0033's amendment records the second push, refusals, no-op logging, continued review numbering, accumulated metrics and recovery after a stopped update.

## Proposed learnings (not decided)

- Proposed: Test concurrent mutations between the final validation and the external write; an earlier read does not enforce an atomic precondition.
- Proposed: Validate individual commits when a requirement constrains history, rather than relying on the endpoint tree diff.
- Proposed: When reusing delivery helpers, test every refusal exception through the new command's outer stop handler.
