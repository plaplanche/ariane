# Product brief: Specify branch update by merge and ticket dependencies for slice 5: new ADR, spec C1, C11, C23 (docs only)

- Source: issue #109 (https://github.com/plaplanche/ariane/issues/109)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

Keeping delivered branches current and running dependent tickets in order is done by hand today. On 2026-10-11 and 12, pull requests #106 and #107 went into conflict with `main` after other merges: by hand, `main` was merged into each branch, conflicts resolved (including a behaviour conflict between #103 and #104 that only tests showed), checks replayed, `ariane verify` run, the branch pushed; CI on Windows then went red on #107 and was fixed the same way. Slice 4's tickets #95 to #100 also depend on each other, and only the session that runs them knows the order. The spec already speaks of updating a branch, but in other terms than the owner decided: C11 says "If the base branch moved, Ariane rebases the ticket branch, runs the project's regeneration command if one is declared, and replays every check; a conflict goes to the human". The owner decided on 2026-10-13: a merge (never a rebase), with conflicts or red checks handed to an implementer session and the result reviewed; dependencies declared in the issue and enforced by refusal; both scheduled at the start of slice 5. This ticket records the decisions only. Spec: C1, C11, C23, roadmap.

## Current state

- `docs/spec.md:109` (C1): the default issue sections are Context, Current state, Decided spec, Release note, Acceptance criteria, Acceptance checklist, Out of scope, Related, optional Budget; no dependency section.
- `docs/spec.md:214` (C11, first bullet): "If the base branch moved, Ariane rebases the ticket branch, runs the project's regeneration command if one is declared, and replays every check; a conflict goes to the human."
- `docs/spec.md:389` (roadmap, slice 5): "C2, C4, C3, per-ticket budget (C5), approve and revise commands (C23)".
- `docs/adr/` ends at `0031-reviewer-isolation.md` (another ticket may add one before this one runs: use the next free number).

## Decided spec

- **A new ADR** at the next free number, `docs/adr/<NNNN>-branch-update-and-ticket-dependencies.md`, status accepted, capabilities C1, C11, C23, with:
  - **Branch update**: `ariane update <n>` merges the remote base branch into `ariane/<n>` with a merge commit (never a rebase, never a force-push), in the ticket's working tree. A clean merge: the checks are replayed in a clean tree and one review runs (as in `ariane verify`); go and green checks: Ariane pushes the branch. A conflict or a red check after the merge: one implementer session resolves it (the conflict or the failure is its task, like a fix round), then replay and review as above, within the fix-round limit of C10; still no-go or red: the ticket stops as "needs a human" and nothing is pushed. Records go to `work/<n>/` like any round. A branch whose pull request is merged or closed is refused.
  - **Dependencies**: an optional issue section "Depends on", listing issue numbers (`#95, #97`). `ariane start` refuses a ticket while one of them is not closed by a merged pull request, naming it, before any branch or agent. Running dependent tickets automatically in order waits for C12.
  - **Placement**: first tickets of slice 5, before C2.
  - **Alternatives considered**: rebase then replay (C11's old text: rewrites a pushed branch, and a person may have checked it out); clean merges only with conflicts to the human (leaves the most frequent case manual); a queue command running tickets in order (already a form of C12, frozen).
- `docs/spec.md` C1: "Depends on" added as an optional section of the default issue format, with the refusal rule in one sentence.
- `docs/spec.md` C11: the first bullet's rebase sentence is replaced by the update rule above in one or two sentences (merge, implementer on conflict or red check, replay and review, push only on go), citing the new ADR.
- `docs/spec.md` C23: `ariane update` added to the list of commands.
- `docs/spec.md` roadmap, slice 5's row: "branch update (C11) and ticket dependencies (C1)" added first to its capabilities; the gate is unchanged.
- No code change.

## Release note

Docs: branch update by merge and ticket dependencies are specified for slice 5 (new ADR).

## Acceptance criteria

- The new ADR holds the decisions above; C1, C11, C23 and the roadmap row read as described; no other part of the spec changes.
- All checks in CLAUDE.md pass.

## Acceptance checklist

- [ ] The new ADR added; `docs/spec.md` C1, C11, C23 and slice 5's roadmap row updated.
- [ ] All checks in CLAUDE.md pass.
- [ ] Definition of done, documentation (C25): only `docs/spec.md` and the new ADR change; `docs/architecture/` unchanged (nothing is built yet).

## Out of scope

Implementing `ariane update` or the dependency check (slice 5 tickets).

## Related

ADR 0017, ADR 0020, ADR 0028, spec C1, C10, C11, C12, C23; pull requests #106, #107.
