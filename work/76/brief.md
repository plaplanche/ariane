# Product brief: Fix the findings of the first review: untrusted paths, globs, generated checks, reviewer cost (C10, C21, C25, C26)

- Source: issue #76 (https://github.com/plaplanche/ariane/issues/76)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

The first full review by Ariane (`work/70/review-0.md`, ticket #70) answered `go` with four minor findings, and the delivery of #33 left one gap in the journal. This issue fixes three of the findings and the gap (the fourth, `modules/logs.md`, needs no change: that file lists no log type, the generated `docs/logs.md` does), before slice 3 goes on. Spec: C10 (review), C21 (untrusted data in prompts), C25 (documentation upkeep), C26 (definition of done), observability NFR (every session's cost is journaled).

## Current state

- `src/ariane/review.py` `prompt`: the documents flagged by `_flag_untouched_docs` (`flow.py`) are listed under "a fact from Ariane", outside the `<untrusted-ticket>` blocks. They can be built from file names the agent created (`{stem}` in the map), so the agent controls free text in the reviewer's trusted section.
- `src/ariane/config.py` `_glob_regex`: `**` becomes `.*`, so `src/**/*.py` is `src/.*/[^/]*\.py` and does not match `src/a.py`.
- `src/ariane/config.py` `_definition_of_done` only accepts `{ check = ... }` names from `[[checks]]`; the generated checks `docs: <name>` (`Documentation.checks`) are refused there. A declared check named `docs: <name>` would also collide with a generated one.
- `src/ariane/flow.py` `_review`: after `self.runtime.run(session)` the reviewer's cost and tokens are not journaled (the implementer's are, under "Implementer session stopped").

## Decided spec

1. Untrusted names: every path in the not-updated list goes inside its own `<untrusted-ticket kind="paths">` block, escaped with the existing `context._escape`; the sentence stating that Ariane found them stays outside the block.
2. Globs: `**/` matches zero or more whole folders (`(?:.*/)?`); a `**` that is not followed by `/` keeps today's meaning. ADR 0026 is amended to say so.
3. Check names: a `[[checks]]` name starting with `docs: ` is refused at load, naming `checks[i].name`. `{ check = "docs: <name>" }` in the definition of done is accepted when `<name>` is a declared `[documentation.generated]` entry.
4. Each reviewer session journals a "Reviewer session <n> stopped: <reason>" entry with its cost and tokens, in the implementer's format; a new log type `ticket.review.stopped` is declared and the log catalogue regenerated.

## Release note

Fixed: names from the agent stay untrusted in the reviewer's prompt; `**/` matches zero folders; generated checks can be definition-of-done items; the reviewer's cost is journaled.

## Acceptance criteria

- Tests named `test_c21_review_paths_*`: a path holding instructions or a closing tag appears only inside an escaped untrusted block of the reviewer's prompt.
- Tests named `test_c25_glob_*`: `src/**/*.py` matches `src/a.py` and `src/x/y/a.py`, not `srcx/a.py` nor `src/a.txt`.
- Tests named `test_c26_dod_generated_*`: `{ check = "docs: refs" }` loads when `refs` is generated and is refused, naming the key, when it is not; a declared check named `docs: x` is refused naming `checks[0].name`.
- Tests named `test_obs_review_cost_*`: the journal records the reviewer's cost and tokens after each session, including an invalid answer's.
- All checks in CLAUDE.md pass.

## Acceptance checklist

- [ ] `uv run pytest -k "c21_review_paths or c25_glob or c26_dod_generated or obs_review_cost"` runs at least 6 tests and they pass.
- [ ] All checks in CLAUDE.md pass.
- [ ] Definition of done, documentation (C25): ADR 0026 amended (globs); `docs/architecture/modules/review.md`, `config.md` and `flow.md` updated; `docs/logs.md` and `docs/reference/` regenerated.

## Out of scope

Choosing the reviewer's runtime from `agents.reviewer.runtime` (only `claude-code` exists; #36). Fix rounds (#34).

## Related

#70, #33, ADR 0016, ADR 0022, ADR 0026, spec C10, C21, C25, C26.
