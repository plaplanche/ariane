# 0012. Measurements per ticket and the report command

- Status: accepted
- Date: 2026-10-07
- Capabilities: C19, C23

## Context
Slice 2 asks for C19's cost, rounds and first-pass verdict; costs are those the agent reported,
never estimates; a command produces a report over a period.

## Decision
`work/<n>/metrics.json`, rewritten by Ariane at each step and committed with the records:
`{"ticket": n, "started": ISO date, "sessions": [{"role", "round", "model", "stop_reason",
"cost_usd" (null when not reported), "input_tokens", "output_tokens", "duration_s"}],
"rounds": number of fix rounds, "first_pass_verdict": "go" | "no-go" | "not reviewed",
"outcome": "delivered" | "stopped" | "needs a human" | "learnings awaiting approval"}`.

`ariane report [--since YYYY-MM-DD]` reads every `work/*/metrics.json` in the current checkout
(the main branch holds merged tickets) and prints one line per ticket and the totals: cost,
agent time, rounds, first-pass go rate. One summary line ends the output (C23).

## Consequences
The report only sees merged tickets unless run on another branch; human waiting time and the
other C19 measures come later.

## Alternatives considered
- Parsing the journal: human text, brittle.
- A database outside the repository: state would not be rebuilt from the folder and git.
