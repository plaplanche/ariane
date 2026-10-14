# Module `ariane.replay`

One round of replay and review of a ticket, moved out of `flow` unchanged (ADR 0034): the checks in a clean working tree (C9), then the read-only reviewer on a separate tree (C10, C26).

## Main types and functions

- `replay`: sets up and runs every check in a clean working tree at the delivered commit and returns the tree, kept for the reviewer.
- `review_round`: review `round_` on the reviewer tree; writes `review-<round>.md`, journals the verdict and tells the metrics the first-pass verdict.
- `remove`: removes a replay or reviewer tree, journaling a warning if it cannot.

## Collaborations

Arrows go from the caller to the callee.

```mermaid
flowchart LR
  replay --> checks
  replay --> delivery
  replay --> git
  replay --> metrics
  replay --> review
  replay --> review_session
  replay --> stop
  replay --> ticket
  flow --> replay
```

## Serves

C9, C10, C26; ADR 0018, ADR 0027, ADR 0031, ADR 0034. See [the component view](../3-components.md).
