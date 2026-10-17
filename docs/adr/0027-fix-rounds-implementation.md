# 0027. Fix rounds implementation choices

- Status: accepted
- Date: 2026-10-10
- Capabilities: C10

## Context
ADR 0010 and ADR 0016 fix the fix rounds: at most two, then a draft pull request. A few details were left open.

## Decision
- A fix round is a fresh implementer session in the ticket's working tree, with the implementer's configuration. Its prompt adds the last review's findings (and the blocking checks that failed) in an escaped `<untrusted-ticket kind="findings">` block: they come from an agent that read untrusted text, so they are data.
- The guards, the commit of the agent's work and the clean-tree replay run after each fix session as after the first one. Nothing is pushed before the delivery, so the branch is pushed once.
- Blocking checks that fail after a fix round make a negative round: that commit is not reviewed, and the next fix round (if any) gets the previous review's findings plus the failing checks. Blocking checks failing after the first session still stop the ticket, as before.
- Review `n` is recorded in `work/<n>/review-<round>.md`, rounds counted from 0. The pull request links the last review.
- After the last round, a review still `no-go` (or blocking checks still failing) is delivered as a draft pull request: the same body, with a "Needs a human" paragraph, the ticket status `needs a human` and the next action "finish by hand, then run `ariane verify`". The command exits 1 because the ticket is not ready to merge.
- The tracker interface gets `draft` on `open_pull_request`; `InMemoryTracker` records it.
- A fix session that does not finish, or a guard that fails, stops the ticket without a pull request, as for the first session.

## Consequences
A ticket costs up to three implementer and three reviewer sessions. The human always gets the branch and the findings in one place.

## Alternatives considered
- Review the commit whose checks failed: rejected, its verdict would be about a state that cannot be delivered.
- Push after each round: rejected, the push guard and C11 want one push.

## Amendment: a fix round that changes nothing (ticket #135)
- `_fix` takes the head before the fix session and after Ariane's commit. When they are equal the round made no change (an agent that commits by itself moves the head, so it is not "unchanged"). The journal gets `ticket.fix.unchanged` with the session's summary, no replay and no review run, and the ticket is delivered as when the rounds are exhausted: a draft pull request with the last review and the last replayed results, status `needs a human`; the stop line says "fix round N changed nothing".
- `metrics.json` keeps `rounds` and gains `unchanged_fix_rounds`. A session that stopped for budget, turns, timeout or error keeps the earlier behaviour.
- Rejected: rerunning the fix session once, told that it changed nothing. The simplest design stops; the human reads the summary.
