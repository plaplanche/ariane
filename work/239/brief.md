# Product brief: Types on Windows as a check: `mypy --platform win32` in Ariane's replay (C9)

- Source: issue #239 (https://github.com/plaplanche/ariane/issues/239)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

Twice in October a change passed every check of Ariane's replay on Linux and then failed the type check on the Windows CI jobs: an `os.O_NOFOLLOW` that Windows lacks, and a narrowing that held only on Linux (pull request #227). Each cost a CI round and a hand fix. `mypy --platform win32` on Linux finds both, and has been run by hand before every push since. The owner asked for it to become a check. Spec: C9 (checks replayed), CLAUDE.md rule 6 (the same checks on Windows, macOS and Linux).

## Current state

- `ariane.toml` declares `types` as `uv run mypy`; CLAUDE.md's "Checks" table lists the same five checks.
- The CI's Windows jobs run `uv run mypy` natively, which is where these errors show today.

## Decided spec

- **A sixth check.** `ariane.toml` gets a blocking check `types (Windows)`, `uv run mypy --platform win32`, after `types`, with the same `paths` as `types` if it has any; the definition of done gets `{ check = "types (Windows)" }`.
- **CLAUDE.md.** The "Checks" table gets the row `| Types (Windows) | `uv run mypy --platform win32` |`, with a note that in CI the Windows jobs' native `uv run mypy` covers it, so the workflow does not change.
- No workflow change.

## Release note

None (Ariane's own checks).

## Acceptance criteria

- `ariane.toml` and CLAUDE.md list the same checks (a test, if one compares them, is updated).
- `uv run mypy --platform win32` passes on the branch.
- All checks in CLAUDE.md pass.

## Acceptance checklist

- [ ] The new check in `ariane.toml` and in the definition of done.
- [ ] CLAUDE.md's "Checks" table has the row and the note.
- [ ] All checks in CLAUDE.md pass.
- [ ] Definition of done, documentation (C25): CLAUDE.md and the README where it lists the checks; no module documentation affected.

## Out of scope

- Other platforms (`darwin`): no macOS-only type error was seen.
- Changing `.github/workflows/`.

## Related

Pull request #227 (the Windows-only type errors), spec C9, CLAUDE.md rule 6.
