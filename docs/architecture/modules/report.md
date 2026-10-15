# Module `ariane.report`

`ariane report [--since YYYY-MM-DD]` (C19, C23, ADR 0035): reads the metrics files of the checkout and prints one line per ticket, then totals, then one summary line.

## Main types and functions

- `build(root, since)`: returns a `Report` (lines, exit code). Reads `work/*/metrics.json` and `work/verify/**/metrics.json` (a hand-takeover record shows its branch), keeps tickets started on or after `since`, prints number, mode, outcome, cost ("partly not reported" when a session's cost is null), agent time, rounds and first-pass verdict. Totals give tickets, cost, agent time, rounds and the first-pass go rate (go / reviewed). A file that cannot be read or has a field of the wrong type is named and skipped, and the exit code is 1.

- `build(root, since, tracker)` also reads the shadow clones (`<repo>.ariane/shadow/<n>/work/<n>/metrics.json`) and prints, before the totals, `Human time:` (waiting, restarts, shadow minutes judged, per merged pull request), `Gates bypassed:` and the `Shadow:` totals with `shadow pass: yes|no` (C19, ADR 0038). Each delivered ticket's line gets its human time and gates bypassed; a shadow ticket's line gets its judgement. Without a tracker (no token, no configuration) or when it fails, the waiting time reads "not available".

## Collaborations

Arrows go from the importing module to the imported module; a dashed arrow is an import for type checking only.

<!-- generated: collaborations -->
```mermaid
flowchart LR
  cli --> report
  report --> measures
  report --> metrics
  report --> shadow
  report --> ticket
  report --> tracker
```
<!-- end generated -->

## Serves

C19, C23; ADR 0012, ADR 0030, ADR 0035, ADR 0038. See [the component view](../3-components.md).
