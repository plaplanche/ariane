# 0009. Slice 2 plan: tickets, order and gate evidence

- Status: accepted
- Date: 2026-10-07
- Capabilities: C10, C18, C19, C21 (basic), C9

## Context
Slice 2 (dogfooding, learnings, review) adds C18 (file store), C10 (one reviewer), C19 (cost,
rounds, first-pass verdict) and the redaction of everything posted (C21, basic); C9's commit
statuses already shipped (#7, #8). Its gate: "Ariane's own tickets go through Ariane". From this
slice on, every Ariane ticket goes through Ariane (CLAUDE.md rule 3), so the slice is a series of
issues that Ariane implements, each a small vertical step.

## Decision
Nine issues, in this order, each run with `ariane start`:

1. **Pure move**: split `flow.py` (403 lines) so the review loop fits under the 600-line limit;
   no behaviour change (non-functional requirement "refactors done as pure moves first").
2. **Redaction (C21 basic)**: one redaction function for known secrets and common token formats,
   applied to everything Ariane posts and everything it writes to the ticket folder (ADR 0013).
3. **One push per ticket**: every record is committed before a single push, so each ticket costs
   one CI run; the pull request link is reported, not committed.
4. **Measurements (C19)**: each session's cost, tokens and duration, the ticket's rounds and
   first-pass verdict, recorded in `work/<n>/metrics.json` (ADR 0012).
5. **Reviewer (C10)**: one read-only reviewer session on a different model after green checks;
   verdict and findings in `work/<n>/review-<round>.md` and in the pull request (ADR 0010).
6. **Fix rounds (C10)**: on a negative verdict, at most two implementer fix rounds, then a draft
   pull request for the human (ADR 0010).
7. **Learnings checkpoint (C18)**: the implementer and the reviewer propose learnings; the ticket
   stops at `learnings awaiting approval`; `ariane learnings` records the answer, writes rules to
   `CLAUDE.md` and facts to the store outside the repository, then delivers (ADR 0011).
8. **Learnings in context (C18)**: facts injected within a size limit; `add-rule` for rules found
   while reviewing a pull request; `docs/learnings.md` migrated (rules to `CLAUDE.md`, facts to
   the store) and removed.
9. **Report (C19)**: `ariane report` over a period, from the tickets' `metrics.json`.

New modules, one per issue (eng review, D1): `delivery.py` (issue 1), `redact.py` (2),
`metrics.py` (4), `review.py` (5 and 6), `learnings.py` and `resume.py` (7), `report.py` (9).

Issues 1 to 5 are reviewed by the owner only (the reviewer exists from issue 5 on); from
issue 6 on, every ticket is reviewed by Ariane's own reviewer.

**Gate evidence**: the nine issues are closed by pull requests Ariane opened; the pull requests
of issues 6 to 9 carry a review by Ariane's reviewer; `ariane report` lists the slice's tickets
with cost, rounds and first-pass verdict; at least one learning was proposed, decided with `ariane learnings`
before the push, and an accepted rule or fact appears in a later ticket's context (journal);
each slice 2 ticket after issue 3 has exactly one push.

## Consequences
Each step is small enough for one implementer session. The reviewer only exists from issue 5 on,
so issues 1 to 5 rely on the replayed checks and the owner's review.

## Alternatives considered
- One large ticket per capability: too big for one session and one review.
- Reviewer first: its findings would be posted before redaction exists.
