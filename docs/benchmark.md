# Benchmark: Ariane against Claude Code alone

Status: lot 1 done for two attempts, the others running (16 October 2026).

## Question

Does Ariane deliver a ticket faster, cheaper and better than Claude Code used alone, and where does it lose time? The answer is measured on a reference project, not on Ariane itself, so that the measure does not depend on Ariane's own history.

## Method

- **Reference project**: a two-language service (a TypeScript Worker and a Python node, with Playwright end-to-end tests), specified in a frozen spec per lot and run locally with mocks only.
- **Tickets**: lot 1 has six tickets (skeleton and checks, shared contracts, subtitle cleaning, sponsor segments, extractors, end-to-end command). Every attempt gets the same tickets, in the same order.
- **Attempts**, each in its own repository with its own CI (a fixed workflow runs the jobs the agents list in `ci/jobs.json`):

| Attempt | Setup |
| --- | --- |
| A0 | Claude Code alone, Opus, one fresh session per ticket |
| A1 | Ariane: Sonnet implements, Opus reviews, up to two fix rounds |
| A2 | Ariane with the reviewer on opencode (GPT-5) |
| A3 | Claude Code alone, Sonnet: isolates the effect of the model |

Each attempt is repeated three times to measure variance.
- **Judge**: a private oracle the agents never see: black-box acceptance tests run against the attempt's command with unseen fixtures (27 tests for lot 1), and a quality grid graded blind by a read-only reviewer on anonymised copies.

## Results so far (lot 1)

| Measure | A0, Opus alone | A1, Ariane |
| --- | --- | --- |
| Cost (six tickets) | $7.49 | $6.45 |
| Red CI before merge | 0 | 0 |
| Fix rounds | none | 8 |
| Hidden acceptance | 25 / 27 | 27 / 27 |
| Quality grid (out of 25) | 22 | 18 |

- Ariane's reviewer caught, before any human looked: a CI that would have broken (dependencies missing in isolated jobs), a 2.000 s gap compared as floats, network failures not caught, real tool errors mis-mapped, and spec rules without a test.
- The blind grading puts Ariane ahead on spec conformance (4 against 3) and Claude Code alone with Opus ahead on tests, readability and CI (5 against 3 or 4). A3 (Sonnet alone) will tell whether the gap comes from the model or the process.
- On a small ticket the review dominates the cost: $0.78 of $0.88 on ticket 1.

## Defects found in Ariane

- The replay runs the checks one after another in one tree, so it cannot see that an isolated CI job would lack its dependencies.
- The cost of the review is not proportionate to the size of the ticket.
- Ariane's own `VIRTUAL_ENV` leaks into the checks of the project it works on.
- The journal entries written after delivery are never committed.

Each becomes an Ariane ticket once lot 1 is judged on every attempt.

## Next

Lot 2 (the Worker, the node protocol, OAuth against a fake identity provider, the first end-to-end tests) on A0, A1, A2 and A3; then a lot run by two people in parallel on the same repository, where Ariane is expected to pay off.
