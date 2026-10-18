# Product brief: Faster CI: parallel tests (pytest-xdist) everywhere, Python 3.11 on Linux only, uv cache (C9)

- Source: issue #187 (https://github.com/plaplanche/ariane/issues/187)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

Every pull request waits about 30 minutes for CI. The `CI` workflow runs 6 jobs (`ubuntu-latest`, `macos-latest`, `windows-latest` × Python 3.11 and 3.13); the tests take about 4 minutes on Linux and 23 to 26 minutes on Windows (1,375 to 1,611 s on the recent pull requests #171 to #183). No single test dominates (the slowest is 7 s); the time is spread over about 600 tests that each start git and processes, which is slow on Windows. The same suite is replayed by Ariane on every ticket (C9) and again by the `Check statuses` workflow. The owner decided: run the tests in parallel everywhere, and keep Python 3.11 on Linux only. Spec: C9 (checks); CLAUDE.md rule 6 (CI runs the checks on Windows, macOS and Linux).

## Current state

- `pyproject.toml`: `[tool.pytest.ini_options] testpaths = ["tests"]`; dev dependencies `pytest`, `ruff`, `mypy`.
- `.github/workflows/ci.yml`: matrix `os: [ubuntu-latest, macos-latest, windows-latest]`, `python: ["3.11", "3.13"]`, `fail-fast: false`; `astral-sh/setup-uv@v6` without cache; steps install, lint, format, types, `uv run pytest`, file length, then a Windows smoke test.
- `.github/workflows/check-statuses.yml`: replays the checks on `ubuntu-latest` for `ariane/` branches.
- `ariane.toml` and CLAUDE.md run the tests with `uv run pytest` (`-q` in `ariane.toml`).

## Decided spec

- **Parallel tests everywhere:** add `pytest-xdist` to the dev dependencies (`uv.lock` regenerated with `uv lock`) and `addopts = "-n auto"` to `[tool.pytest.ini_options]`, so `uv run pytest` runs in parallel in CI, in Ariane's replay and locally. `-n 0` still runs serially.
- **The tests hold under xdist:** every test passes with `-n auto` on Linux, macOS and Windows. A test that cannot run concurrently (a shared global, a fixed port or path, the process tree of the pytest process) is fixed to use per-test state, or, if it cannot be, marked with `@pytest.mark.xdist_group` and the suite run with `--dist loadgroup`; the ADR names each such test and why.
- **Matrix:** Python 3.13 on the three systems, plus Python 3.11 (the minimum, `requires-python`) on `ubuntu-latest` only: 4 jobs instead of 6. Rule 6 still holds (Windows, macOS and Linux).
- **Cache:** `astral-sh/setup-uv` with `enable-cache: true` in both workflows.
- **ADR 0046** (number to confirm at merge): parallel tests, the reduced matrix and why, the measured durations before and after.

## Delivery note

A push touching `.github/workflows/` is refused from a cloud session (CLAUDE.md, "Cloud sessions"). The implementer changes `pyproject.toml`, `uv.lock`, the tests and the documentation, and writes the two workflow changes in the ADR as the exact YAML to apply; the owner commits `ci.yml` and `check-statuses.yml` from their machine in the same pull request (a hand takeover, CLAUDE.md).

## Release note

Changed: the tests run in parallel (`pytest-xdist`, `-n auto`), and CI runs Python 3.11 on Linux only; a pull request's CI goes from about 30 minutes to the target below.

## Acceptance criteria

- `uv run pytest` runs with `-n auto` and passes on Linux, macOS and Windows in CI; `uv run pytest -n 0` passes too.
- The longest CI job of the pull request takes under 12 minutes (Windows today: about 26), measured on the pull request's own CI and recorded in the ADR with the before and after durations.
- CI runs 4 test jobs: Linux 3.11, Linux 3.13, macOS 3.13, Windows 3.13.
- All checks in CLAUDE.md pass.

## Acceptance checklist

- [ ] `pytest-xdist` in the dev dependencies and `-n auto` in `addopts`; `uv.lock` regenerated.
- [ ] Every test passes in parallel; any test grouped with `xdist_group` is named in the ADR.
- [ ] `ci.yml` and `check-statuses.yml` updated (by the owner, from the YAML in the ADR).
- [ ] ADR 0046 (or the next free number) with the durations before and after.
- [ ] All checks in CLAUDE.md pass.
- [ ] Definition of done, documentation (C25): README's development section (the tests run in parallel; `-n 0` to run serially); CLAUDE.md "Checks" table if the command changes; `docs/architecture/` if a module changes.

## Out of scope

- Selecting which checks run for a ticket (#184, #185, #186).
- Replaying independent checks in parallel inside Ariane (#143).

## Related

Spec C9; CLAUDE.md rule 6; #143, #184.
