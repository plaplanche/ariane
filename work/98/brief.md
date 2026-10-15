# Product brief: Add ariane judge <n> accept|reject --minutes N for shadow tickets (C19, C23, slice 4)

- Source: issue #98 (https://github.com/plaplanche/ariane/issues/98)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

ADR 0030 item 5: the human judges each shadow diff and says how long it took; these are the shadow pass criterion ("diff judged acceptable in at least 8 of 10") and Ariane's human time on shadow tickets. Needs the shadow mode ticket of slice 4 merged first. Spec: C19, C23.

## Current state

- After shadow mode: `<repo>.ariane/shadow/<n>/work/<n>/metrics.json` holds a shadow ticket's measurements; nothing records the human's verdict.
- `src/ariane/cli.py:61`: subcommands `start`, `status`, `verify` (and `report`).

## Decided spec

- `ariane judge <n> accept|reject --minutes N [--note TEXT]` writes into the shadow ticket's `metrics.json`: `"judgement": {"verdict": "accept" | "reject", "minutes": N, "note": TEXT or null, "at": ISO-8601 UTC}`.
- `--minutes` is required, an integer from 0 to 1440. Judging again replaces the judgement and keeps the earlier ones in `"judgements_before"`.
- No shadow clone for `<n>`, or a clone whose ticket is still `running`: one line saying so, exit 1. One line on success, exit 0.

## Release note

New: `ariane judge <n> accept|reject --minutes N` records the human's verdict and time on a shadow ticket.

## Acceptance criteria

- Tests named `test_c19_judge_*` show: accept and reject written with minutes and note; minutes missing, negative or above 1440 refused; unknown ticket; running ticket; judging twice keeps the earlier judgement.
- All checks in CLAUDE.md pass.

## Acceptance checklist

- [ ] `uv run pytest -k c19_judge` runs at least 5 tests and they pass.
- [ ] All checks in CLAUDE.md pass.
- [ ] Definition of done, documentation (C25): `docs/reference/cli.md` regenerated, module docs updated, README's shadow section mentions `ariane judge`.

## Out of scope

The report's use of judgements (next ticket).

## Related

ADR 0030 (item 5), spec C19, "Adopting Ariane on an existing project" step 2.
