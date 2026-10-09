# 0020. Roadmap revision: order, frozen capabilities, success measure, developing Ariane

- Status: accepted
- Date: 2026-10-08
- Capabilities: all (roadmap); C2, C4, C5, C9, C10, C17, C18, C19, C23

## Context
An outside review of the repository proposed to bring forward the gates that other tools do
not offer (C2, C4, C9 complete, C17), to measure Ariane against the current way of working, to
freeze capabilities nobody needs yet, and to make Ariane's own development use Ariane's gates.
Vendor independence and the runtime-neutral contract (ADRs 0014, 0015) must come before the
reviewer is built. A second user will run Ariane on macOS on their own repository.

## Decision
**Order of the next work** (owner's choice), replacing the plan of ADR 0009 from its issue 3:
1. One push per ticket (#22).
2. Clean-tree replay of the checks; statuses from a replay (ADR 0018).
3. Cache tokens counted (C5); shorter records and a status that does not go stale (ADR 0019);
   what the second user needs to install and run Ariane (ADR 0021).
4. Runtime-neutral contract and login variables per runtime (ADR 0015).
5. Reviewer and fix rounds on Claude Code (ADR 0016).
6. `ariane verify <branch>` for branches finished by hand (ADR 0016).
7. The reviewer on opencode (ADR 0014).
8. Measurements (C19, ADR 0012) and a shadow mode, for the success measure below.
9. Stages and approvals, slices and risk depth (C2, C4, C3).
10. C9 complete (tests replayed on the code before the change, mechanical checklist, coverage)
    and the rules judge (C10).
11. Mastery explanation and quiz (C17).
12. Learnings (C18, ADR 0011), declared skills (C6) and project instructions (C22).
13. Security complete (C21) with the operating-system sandbox (ADR 0017), and C24 if unfrozen.

The spec's roadmap table is rewritten with these steps grouped into slices 2 to 9.

**Frozen capabilities.** Their text stays in the spec, marked frozen with the condition that
unfreezes it: GitLab (a user on GitLab), C7 agent teams (a ticket whose plan has two independent
slices worth running in parallel), C12 autonomous mode (the owner decides, on the success measure's numbers, that tickets may run without a person starting them), C13 several
machines (a second machine running tickets for the same repository), C14 labels (C12
unfrozen), C15 post-deployment monitoring (a user project that Ariane delivers to production),
C16 release notes (a project that publishes releases), C20 periodic reviews (fifty tickets
delivered by Ariane on one project), C24 setup assistant (a third user).

**Success measure for Ariane itself.** Over the second user's first 10 tickets, in shadow mode
("Adopting Ariane on an existing project"), Ariane is compared with that user's current process
on two numbers: human time per merged pull request, and the count of steps skipped or gates
bypassed. Both are reported by `ariane report`; the current process is measured by a short log
the user keeps. There is no automatic stop rule: the owner decides on the numbers.

**Developing Ariane with Ariane.** The repository has no hooks of its own. Ariane is used on
its own tickets as soon as each capability exists, so the gates are Ariane's, not the
session's:
- In CLAUDE.md, each manual rule that a shipped capability enforces is removed or replaced by
  "enforced by Ariane (Cn)", and the next ticket after a capability ships uses it.
- A hand takeover (after a second `no-go`, or a ticket Ariane cannot run, such as a change to a
  workflow file pushed from the owner's machine) runs `ariane verify <branch>` before the pull
  request once it exists (step 6); until then, the session's checks and independent review
  stay manual.

This decision supersedes ADR 0009. ADRs 0011, 0012 and 0013 keep their decisions; 0011 and 0012
move to the steps above.

## Consequences
The reviewer comes later than in ADR 0009, after the contract that makes it vendor-neutral.
Frozen capabilities cost nothing until their condition is met. The gate of each slice in the
spec's roadmap is the evidence that it works on Ariane's own tickets.

## Alternatives considered
- Keep ADR 0009's order (reviewer on Claude Code first): faster to a review, but its contract
  would be rewritten when opencode arrives.
- Remove the frozen capabilities: loses the decisions already written for them.
- A stop rule tied to the success measure: rejected by the owner; the numbers inform, the owner
  decides.

## Amendment (2026-10-09)
The owner postponed the second user to slice 4 to build features first: the installation moves
from slice 2's gate to slice 4's. Slice 2 closed with #25 (a hand takeover for a workflow file,
pushed by bundle) and #29 (a second hand commit on the README, at the owner's request) as
documented exceptions to "pushed once".
