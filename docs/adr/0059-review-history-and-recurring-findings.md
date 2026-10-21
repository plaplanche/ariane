# 0059. Review history to the fix rounds, and recurring findings

- Status: accepted
- Date: 2026-10-21
- Capabilities: C10, C19

## Context
A fix round was a fresh implementer session that saw only the last review's findings, and the
next reviewer saw only the new head. When a fix caused the next finding (a moved write that left
the race, then an intermediate state that broke the writes relying on the old invariant), neither
session knew it: the implementer did not see that its previous fix caused the new finding, and the
reviewer did not say "same problem, third time". The ticket ended as a draft pull request after
two rounds with nothing telling the human that the rounds had circled on one design question.
C10 bounds the rounds at two; C19 asks for the failure causes per ticket.

## Decision
- **History to both sessions.** Ariane keeps the reviewed rounds of a run (`review_history.Round`,
  in `_TicketRun.reviews`). Each blocking finding of a reviewed round gets an identifier
  `<round>.<n>` (`n` from 1, in the order of the settled findings, the unmet definition-of-done
  items included).
  - A fix session's findings block lists the blocking findings of every reviewed round before the
    last review (round, file, title), then the last review's findings in full, in the same
    untrusted envelope. Its prompt adds one rule, outside the envelope (`context.RECHECK_RULE`):
    when a fix changes a design (a new state, a moved write, a changed invariant), re-check every
    place that relied on the old one, and say in the summary which places were checked.
  - From round 1 on, the reviewer's prompt lists the earlier rounds' blocking findings with their
    identifiers, in an untrusted `kind="earlier-findings"` block, and asks for one answer each.
- **Three answers.** The reviewer's answer has an optional `earlier` array, one entry per listed
  finding: `finding` (the identifier), `answer` (`fixed`, `still open`, `replaced`) and, for
  `replaced` only, `caused`, the indexes (from 0) of the blocking findings of this answer that the
  fix caused. A missing or doubled entry, an unknown identifier, an unknown answer, a `replaced`
  without `caused` or a `caused` index that is not a blocking finding is an invalid answer, asked
  again once like any other (C10). On round 0 the array may be missing.
- **Recurring.** A blocking finding of the last review is recurring when the reviewer answers it
  `still open` (an earlier finding) or when a `replaced` entry names it in `caused`. Its chain
  follows the `replaced` answers of every round back to the oldest finding.
- **Said, not acted on.** When the last review of a draft has recurring findings, the journal
  records `Review circled on <files>` (`ticket.review.circled`) with the chains, and the draft pull
  request body says, above the review table, that the rounds circled on the same design question
  and lists each chain (round, finding). `metrics.json` records `recurring_findings`, the count of
  the last review (0 when none), and `ariane report` shows it on the ticket's row. The review
  record `review-<round>.md` lists the answers and the chains. The number of rounds
  (`MAX_FIX_ROUNDS = 2`) and the hand-over rule do not change.

## Consequences
- A fix session knows when its earlier fix caused the current finding, and a reviewer must say,
  for each earlier finding, what became of it: a circling run is visible in the pull request and
  counted in the report.
- Every round from 1 asks more of the reviewer: an answer that forgets an earlier finding is
  refused and asked again, at the cost of one more session.
- The history covers one run: an `ariane update` starts its own (it is a new run of the ticket),
  and the original run's rounds are not listed to it.
- A canned answer of the test runtime without `earlier` answers every listed finding `fixed`.

## Alternatives considered
- Giving the history to the fix session only: the reviewer would still not tie the new finding to
  the earlier fix, and nothing could say that the rounds circled.
- Two answers (`fixed`, `still open`): a fix that moved the problem is neither, and it is the case
  that circles.
- Stopping at the first recurring finding, or adding a round when the rounds circle: the bound of
  C10 and the hand-over rule are the owner's; a recurring finding is a fact for the human who takes
  the draft over, not a reason for Ariane to decide differently.
- Reading the earlier rounds back from `work/<n>/review-<round>.md`: the files are records for
  humans, and the run already holds the settled reviews.
