# Review 0

- Reviewed commit: `8b442c6928fdaeb8ef288460a0a3875adef824bb`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/pi.py:97`) The configured dollar budget is never enforced

  PiRuntime passes only max_tokens to Events and never uses session.max_budget_usd. C5 and ADR 0015 require stopping on reported cost when available. A read-only parser probe with 20 tokens and cost.total=100 returned False with no cap under a 100000-token limit; even a $1 session budget cannot stop it. The sequence is: pi makes a billable request, message_end reports its cost, Ariane accumulates that cost but checks only tokens, then pi can make another billable request. Pass the dollar cap into Events, enforce it after each message_end, and test a cost-cap stop independently of the token cap.

- **minor** (`src/ariane/pi.py:234`) Explicitly reported zero cost becomes unknown cost

  reported_cost converts cost.total=0 to null. The ticket and ADR 0015 distinguish a reported cost from no reported cost; a free model reporting zero should retain 0 in metrics. The new zero-cost test instead asserts the incorrect behavior. Track whether a cost was reported separately from its accumulated value, and test both missing and explicitly zero cost.

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

  The new test_c5_pi tests exercise runtime routing, fake-CLI reviews, credentials, token caps, process-tree termination and isolation; the base lacks PiRuntime and rejects pi configuration. Ariane reports passing tests. Dollar-cap coverage is missing. I performed read-only parser probes, without rerunning tests that write files.

- met: The documentation the change affects is updated (C25).

  README, example configuration, generated schema, architecture views, affected module documentation and the reviewer-isolation amendment are updated. Ariane reports the generated-reference check passing. Review ordering remains: instruction journal, session-start journal, CLI execution and cleanup, metrics write, session-stop journal, guard verification, then verdict acceptance or invalid-answer retry.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0051 records the available ADR number, stdin prompt transport, verified CLI version, authentication mapping, event fields, retry handling and isolation choices. Its zero-cost decision conflicts with the reporting requirement noted above.

## Proposed learnings (not decided)

- Test runtime budget enforcement with independent token-cap and reported-cost-cap cases.
- Represent missing usage separately from explicitly reported zero usage.
