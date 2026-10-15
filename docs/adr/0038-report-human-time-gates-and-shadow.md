# 0038. Human time, gates bypassed and shadow results in the report

- Status: accepted
- Date: 2026-10-15
- Capabilities: C19

## Context
ADR 0030 items 2, 6 and 7 name the report's success numbers; the spec leaves the details open.

## Decision
- The tracker gains `pull_request_state(branch)` (opened, ended, merged); the delivered ticket's
  branch is `ariane/<n>`. `ariane report` builds a tracker when `ariane.toml` loads and the token
  variable is set; otherwise (or on a tracker failure) the waiting time reads "not available" and
  the rest still prints. An open or absent pull request waits 0.
- A stop is a `steps` entry `outcome: <status>` other than delivered, needs a human or running; it
  is counted up to the earliest later `started` of a `verify` record of the same ticket or branch.
  A fresh `ariane start` rewrites the ticket's metrics, so only a `verify` is seen as a restart.
- Delivery writes `blocking_red_at_delivery` into `metrics.json`.
- Merged while no-go: the pull request merged and the last `verify` record of its branch is
  no-go, or there is none and the ticket's outcome is `needs a human`. The head is not compared.
- Shadow pass needs ten shadow tickets; fewer reads "no". The window is the last ten shadow
  tickets overall, not filtered by `--since`.
- Shadow clones are full checkouts: only `shadow/<n>/work/<n>/metrics.json` of mode `shadow` is read.
- After the first tracker failure the report asks no more per ticket.

## Consequences
Per-ticket lines get a suffix; the new total lines come before `Totals:`.

## Alternatives considered
Comparing the merged head with the reviewed head: needs the review's commit in the metrics, for
little gain.
