# 0037. The judge command

- Status: accepted
- Date: 2026-10-15
- Capabilities: C19, C23

## Context
ADR 0030 item 5: the human judges each shadow diff and says how long it took. These are the shadow
pass criterion and Ariane's human time on shadow tickets.

## Decision
- `ariane judge <n> accept|reject --minutes N [--note TEXT]` is `shadow.judge`. It writes
  `judgement` (`verdict`, `minutes`, `note`, `at` in UTC) into the shadow ticket's `metrics.json`.
- `--minutes` is required, a whole number from 0 to 1440; argparse refuses anything else (exit 2).
- Judging again moves the earlier judgement to the end of `judgements_before`.
- No shadow clone, or a ticket whose outcome is still `running`: one line, exit 1.
- The file is edited in place and not committed: the judgement is the human's, made after Ariane's
  run ended.

## Consequences
The report can read verdicts and minutes from `metrics.json` (next ticket). Metrics written by a
later Ariane step would not keep the judgement, but a shadow ticket is not run again once judged.

## Alternatives considered
- A separate judgements file: a second place to read per ticket, for no gain.
- Committing the judgement in the clone: it would put a human act in Ariane's history.
