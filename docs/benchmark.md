# Benchmark: Ariane against Claude Code alone

Status: lots 1 and 2 done (17 October 2026).

## Question

Does Ariane deliver a ticket faster, cheaper and better than Claude Code used alone, and where does it lose time? The answer is measured on a reference project, not on Ariane itself, so that the measure does not depend on Ariane's own history.

## Method

- **Reference project**: a two-language service (a TypeScript Worker and a Python node, with Playwright end-to-end tests), specified in a frozen spec per lot and run locally with mocks only.
- **Tickets**: lot 1 has six tickets (skeleton and checks, shared contracts, subtitle cleaning, sponsor segments, extractors, end-to-end command). Lot 2 has ten (local Worker with its database and object store, local stack and e2e check, node protocol with leases, results and expiry, node daemon, a fake OpenID provider with invites, the OAuth authorization flow, the token endpoint, the MCP endpoint). Every attempt gets the same tickets, in the same order.
- **Attempts**, each in its own repository with its own CI (a fixed workflow runs the jobs the agents list in `ci/jobs.json`):

| Attempt | Setup |
| --- | --- |
| A0 | Claude Code alone, Opus, one fresh session per ticket |
| A1 | Ariane: Sonnet implements, Opus reviews, up to two fix rounds |
| A2 | Ariane with the reviewer on opencode (GPT-5) |
| A3 | Claude Code alone, Sonnet: isolates the effect of the model |

Lot 1 ran three times on A0, A1 and A3 to measure variance; lot 2 ran once on each attempt.
- **Rules**: a pull request is merged once its CI is green; a red CI is counted and sent back to the attempt (a message to the session for A0 and A3, a rerun with the failure in the issue for A1 and A2, since Ariane has no CI feedback loop), never fixed by hand. Infrastructure incidents (container restarts, a port clash between two runs on one machine, bugs in the bench's own scripts) are logged and not counted against any attempt.
- **Judge**: a private oracle the agents never see: black-box acceptance tests run against the attempt with unseen fixtures (27 tests for lot 1, 147 for lot 2, lot 1's replayed for regressions), and a quality grid graded blind by a read-only reviewer on anonymised copies. When an oracle test turned out to require something the spec does not say, it was fixed and every attempt was judged again.

## Results, lot 1

| Measure | A0, Opus alone | A1, Ariane | A3, Sonnet alone | A2, Ariane with GPT-5 |
| --- | --- | --- | --- | --- |
| Hidden acceptance (three runs) | 27, 27, 27 / 27 | 27, 27, 25 / 27 | 25, 25, 27 / 27 | 25 / 27 (one run) |
| Cost, first run | $7.49 | $6.45 | — | — |
| Red CI before merge, first run | 0 | 0 | 0 | 1 |
| Handovers (draft after two no-go reviews) | — | 0 | — | 1 |
| Quality grid, first run (out of 25) | 22 | 18 | — | — |

- The one rule most runs missed is a logging rule (attributes of one log line when there is no transcript): four runs out of ten, Ariane's included.
- Ariane's reviewer caught, before any human looked: a CI that would have broken (dependencies missing in isolated jobs), a 2.000 s gap compared as floats, network failures not caught, real tool errors mis-mapped, and spec rules without a test.
- The blind grading puts Ariane ahead on spec conformance (4 against 3) and Claude Code alone with Opus ahead on tests, readability and CI (5 against 3 or 4).
- On a small ticket the review dominates the cost: $0.78 of $0.88 on ticket 1.

## Results, lot 2

| Measure | A0, Opus alone | A3, Sonnet alone | A1, Ariane | A2, Ariane with GPT-5 |
| --- | --- | --- | --- | --- |
| Tickets merged | 10 / 10 | 10 / 10 | 10 / 10 | 7 / 10 (stopped at ticket 8) |
| Hidden acceptance | 147 / 147 | 147 / 147 | 147 / 147 | 96 / 147 |
| Lot 1 still passing | 27 / 27 | 25 / 27 | 27 / 27 | 25 / 27 |
| Red CI before merge | 0 | 1 | 1 | 2 |
| Counted reruns | 0 | 0 | 1 | 1 |
| Handovers | — | — | 0 | 1 |
| Cost of merged tickets | $22.12 | $7.90 | $12.51 | $4.90 |
| Wall-clock of merged tickets | 99 min | 75 min | 221 min | 129 min |

- With one person and mocks only, Claude Code alone reached the same hidden acceptance as Ariane, two to three times faster, and with Sonnet for less money. The lot 1 failures still present in lot 2 are the ones each attempt already had.
- In A1 the Opus reviewer is 61% of the cost ($7.60 of $12.51); in A2 the GPT-5 reviewer costs little but did not hold the scope (below).
- Every red CI came from what only CI runs: one race in a concurrency test (A3) and, twice, the same wrong browser test (waiting for a page load at a redirect address nothing serves), written by A1 and A2, missed by both reviewers, and impossible to see in Ariane's replay because the browser cannot be installed where the agents work. A1 fixed it on its rerun; A2 did not and stopped, which is the rule.

## Defects found in Ariane

- The replay runs the checks one after another in one tree, so it cannot see that an isolated CI job would lack its dependencies; it is also sequential, which makes a ticket slow.
- The cost of the review is not proportionate to the size of the ticket.
- Ariane's own `VIRTUAL_ENV` leaks into the checks of the project it works on.
- The journal entries written after delivery are never committed.
- The opencode reviewer's default token cap is too low for a normal ticket.
- A stopped or interrupted ticket cannot be restarted without removing its worktrees and branch by hand.
- `ariane start` right after labelling an issue can refuse because the label event is not visible yet.
- No CI feedback loop: a red CI on a delivered pull request means a new issue and a rerun from scratch.
- Nothing tells the reviewer which tests the replay could not run.
- The reviewer does not honour the ticket's "Out of scope", and a fix round that makes no commit is not detected.
- No watchdog on a session that stops making progress (a fix round sat in a shell loop that could never end).
- Two runs on one machine share the project's fixed ports, with no way for the project to isolate them.

Each is an Ariane issue.

## Next

Fix the defects that cost the most time (CI feedback, isolated and parallel replay, review sized to the ticket, scope-aware review), run lot 2 again on Ariane alone to measure them, then a lot run by two people in parallel on the same repository, where Ariane is expected to pay off.
