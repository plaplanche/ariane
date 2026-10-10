# Product brief: Move the second user's installation from slice 2's gate to slice 4's (spec, ADR 0020)

- Source: issue #56 (https://github.com/plaplanche/ariane/issues/56)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

Slice 2's gate (spec roadmap, ADR 0020) ends with "a second user installs Ariane on macOS". On 2026-10-09 the owner postponed the second user: more features first. The spec says "A missed gate is fixed before the next slice starts", so the gate has to change before slice 3 starts. Slice 4 ("Measurement and shadow") already needs the second user: its gate is "The second user's first tickets are measured in shadow mode", and installing comes first. The slice 2 gate review also found two tickets that did not reach GitHub in exactly one push by Ariane: #25 (a hand takeover for a workflow file, allowed by CLAUDE.md, pushed by bundle) and #29 (a second hand commit on the README, at the owner's request).

## Current state

- `docs/spec.md` roadmap table, row "2. Dogfooding": gate "Ariane's own tickets go through Ariane, each pushed once with checks replayed in a clean tree; a second user installs Ariane on macOS".
- Row "4. Measurement and shadow": gate "The second user's first tickets are measured in shadow mode".
- `docs/adr/0020-roadmap-revision.md` "Decision", item 3, includes "what the second user needs to install and run Ariane (ADR 0021)" (delivered by #29); nothing says when the install itself happens.

## Decided spec

- Slice 2's gate becomes "Ariane's own tickets go through Ariane, each pushed once with checks replayed in a clean tree (a hand takeover allowed by CLAUDE.md, such as a workflow file, is the exception)".
- Slice 4's gate becomes "A second user installs Ariane on macOS, and their first tickets are measured in shadow mode".
- ADR 0020 gains a short "Amendment (2026-10-09)" paragraph: the owner postponed the second user to slice 4 to build features first; slice 2 closed with #25 and #29 as documented exceptions to "pushed once".

## Release note

Docs: the second user's installation moves from slice 2's gate to slice 4's.

## Acceptance criteria

- The two roadmap rows and ADR 0020 read as above; nothing else in the spec changes.
- All checks in CLAUDE.md pass.

## Acceptance checklist

- [ ] `docs/spec.md` slice 2 gate no longer mentions the second user; slice 4 gate does.
- [ ] ADR 0020 has the amendment paragraph.
- [ ] All checks in CLAUDE.md pass.

## Out of scope

Any other roadmap change.
