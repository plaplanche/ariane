# 0042. A check declares the tests it cannot run locally

- Status: accepted
- Date: 2026-10-17
- Capabilities: C9, C10, C26

## Context
Some tests only run in CI (for example browser end-to-end tests, skipped where the browser cannot
be downloaded). Such a test passed the replay because it was skipped, nobody read it as untested,
and CI went red after delivery.

## Decision
- **A declaration.** The optional key `checks[].not_run_locally` is a non-empty list of path globs
  (same rules as `documentation.map`) naming the files whose tests the check skips when Ariane
  replays it. An empty list or a non-string entry is refused, naming `checks[<i>].not_run_locally`.
- **Records.** `checks.md` adds, under such a check, the globs and the changed files that match
  (or "no changed file matches"). The summary table is unchanged.
- **Reviewer.** When changed files match, its prompt adds a block saying no replay ran them and
  asking for a blocking finding for a test that cannot pass; the paths are given as untrusted data.
- **Implementer.** Its list of checks marks the check and asks for extra care.
- **Declared, not detected.** Ariane does not read the check's output for skips.

## Consequences
The project must keep the list in step with its CI. Ariane still runs none of these tests.

## Alternatives considered
- Detect skips in the check's output: projects word skips differently, and a missed skip would
  read as a run.
