# Module `ariane.measures`

The success measure of `ariane report` (C19, ADR 0038): human time, gates bypassed and shadow results.

## Main types and functions

- `human(data, tracker, takeovers)`: a delivered ticket's `Human` time: `waiting` is the pull request's opening to its merge or close, read from the tracker (None when the tracker is missing or fails; 0 while the pull request is open or absent); `restart_seconds` adds each stop in `steps` to the next `verify` of the same ticket.
- `bypassed(data, takeovers, merged)`: the gates bypassed: a hand takeover per `verify` record of the branch, blocking checks red at delivery, and a merge while the last review on the branch is no-go (the last `verify` go cancels it).
- `shadow_lines(shadows)`: tickets, accept rate, not yet judged, agent push and pull-request attempts, guard violations, then `shadow pass: yes|no` over the last 10 shadow tickets (ten required, no attempt, no violation, at least 8 accepted).

## Collaborations

Arrows go from the importing module to the imported module; a dashed arrow is an import for type checking only.

<!-- generated: collaborations -->
```mermaid
flowchart LR
  measures --> tracker
  report --> measures
```
<!-- end generated -->

## Serves

C19; ADR 0030, ADR 0038. See [the component view](../3-components.md).
