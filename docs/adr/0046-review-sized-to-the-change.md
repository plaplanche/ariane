# 0046. Review sized to the change

- Status: accepted
- Date: 2026-10-18
- Capabilities: C10, C5, C19

## Context
The review is the largest cost of a ticket and did not depend on the ticket's size: in the
benchmark on a reference project (`docs/benchmark.md`), the review cost $0.78 of the $0.88 of a
small ticket, and the reviewer was 61% of the total cost over a lot of ten tickets. C10 requires a
review by a different model whatever the size; it does not require the same depth for a ten-line
change as for a new module. C3 (risk-based depth, slice 5) will choose a depth per ticket later;
until then the review can at least follow the size of the diff. C5 sets a budget per session and
C19 measures the cost.

## Decision
- An optional table `[agents.reviewer.small]` with a required `max_lines` (positive integer) and
  optional `model`, `max_budget_usd`, `max_tokens`, `timeout_minutes`, each replacing the
  reviewer's value for a small change. Any other key, `runtime` and `tools` included, is refused
  naming it: the runtime and the tools stay the reviewer's (a second runtime per round would need
  its own isolation and login). The table is accepted on the reviewer only.
- Before each review round, and in `ariane verify`, Ariane counts the changed lines of the
  reviewed diff (`git.changed_lines`: `git diff --numstat <base> <commit>` without `work/`, added
  plus deleted lines, a binary file counting 0). When the table exists and the count is at most
  `max_lines`, that round's reviewer sessions use the small settings and the prompt gains: "This
  change is small (N changed lines). Review the changed files, their tests and the code that calls
  them; do not survey the rest of the repository." Otherwise nothing changes; without the table,
  behaviour is exactly the previous one.
- The different-model rule still applies: `small.model`, when given, must differ from
  `agents.implementer.model`, refused with the same wording as `agents.reviewer.model` (C10).
  Only the depth of the survey changes, never the independence of the reviewer.
- Idle limit (ADR 0045): the reviewer's `idle_minutes` is kept, except when it is at or above the
  small `timeout_minutes`, where it is dropped: such an idle limit could never stop the session
  before the time limit, so dropping it changes nothing and needs no new key or error.
- A cap stop in a small round names the key that set the cap: `agents.reviewer.small.<key>` when
  the small table gave it, else `agents.reviewer.<key>`.
- Records: the journal entry `ticket.review.started` ends with "small change (N changed lines, at
  most M): small reviewer settings" or "N changed lines"; `metrics.json` records `changed_lines`
  on each reviewer session, next to its model and cost; `review-<round>.md` names the model that
  actually reviewed.
- Ariane's own `ariane.toml` and the example files set no `small` table: the owner chooses the
  values (the example shows it commented).

## Consequences
A small change can be reviewed by a cheaper model with a lower cap, and the reviewer is told not
to survey the whole repository. A change just below the threshold that touches a sensitive module
gets the lighter review too: choosing the depth from what is touched is C3's work. The threshold
counts lines of the whole range, so a fix round that grows the diff past `max_lines` switches the
next round back to the reviewer's own settings.

## Alternatives considered
- Threshold on changed files, or on the diff's characters: lines are what `git diff --numstat`
  measures directly, comparable across languages, and the first signal C3 names for the risk of a
  change; files would treat a one-line change in ten files as large, characters would count long
  generated lines.
- Choosing the depth from labels or touched paths now: that is C3, out of scope here.
- Dropping the different-model rule for small changes: C10 requires it whatever the size.
- A small runtime as well: a second reviewer runtime per round needs its own isolation, login
  variables and instruction snapshot; out of scope.
