# Product brief: Faster tests on Windows: measure, then copy a per-worker template project instead of rebuilding git repositories (C9)

- Source: issue #206 (https://github.com/plaplanche/ariane/issues/206)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

Since #187 (ADR 0048) the tests run in parallel and CI runs four jobs; the Windows job stays the longest by far. On pull request #205 the tests step took 949 s on `windows-latest`, against 123 s on `ubuntu-latest` and 242 s on `macos-latest`, with the same `-n auto`; the Windows job took 16.3 minutes. The owner accepted that for now and asked to make the Windows tests faster later (ADR 0048). The suite computes little: most of its ~700 tests build their own git repositories and start subprocesses (`git`, faux agents), and starting a process and writing many small files cost much more on Windows than on Linux. Every pull request waits for that job, and Ariane's own replay runs the same suite on the owner's Windows machine. Spec: C9 (checks); CLAUDE.md rule 6.

## Current state

- `tests/conftest.py`: the `project` fixture, used by about 30 test modules, starts six git processes per test (`init --bare`, `clone`, `checkout -b`, `add`, `commit`, `push`) before the test does anything; `isolated_git` sets an isolated git configuration per test.
- Many tests then call `git` through `sh(...)` or Ariane's own `git` module several more times.
- Nothing records which tests are slow on Windows.

## Decided spec

- **Measure first.** The `Tests` step of `ci.yml` runs `uv run pytest --durations=30` on every job (the command CLAUDE.md lists stays `uv run pytest`; `--durations` only adds a report). The ADR records the 30 slowest tests on Windows and Linux before the change.
- **A template project per worker.** The `project` fixture builds the bare remote and its clone once per xdist worker (a session-scoped template under the worker's base temp directory), then gives each test a copy (`shutil.copytree`) whose `origin` URL points at the test's own copy of the remote, set with at most one `git` process (`git remote set-url`), or none by rewriting the `url =` line of the copied `.git/config`. Each test still gets a repository nobody else touches; what a test sees (`Project.root`, `Project.remote`, the commit, the branch, the files) does not change.
- **Then the next slowest.** From the Windows measurement, the five slowest tests or fixtures that start avoidable git processes are changed the same way (built once and copied, or fewer calls), without changing what they assert.
- **Then, if still needed, shard the Windows job (owner's go, 18 October).** If the Windows tests step of the pull request's CI is still above 8 minutes after the changes above, the Windows job is split into shards that run in parallel: a `shard` matrix dimension on `windows-latest` only (2 or 3 shards, as few as reach the target), each running one deterministic part of the suite (the `pytest-split` plugin as a dev dependency with its stored durations file, or an equivalent split by test file; the choice and its reason in the ADR). Linux and macOS keep one job each. The job names change, so the ADR lists the new required check names for the owner's ruleset update. If the target is met without shards, the ADR says so and nothing is sharded.
- ADR (next free number): the measurements before and after on the three systems, the template approach, why the copy is safe under xdist, and the shard decision.

## Release note

Changed: the tests build their git repositories once per worker and copy them, so the suite runs faster, mostly on Windows.

## Acceptance criteria

- `uv run pytest` and `uv run pytest -n 0` pass on Linux, macOS and Windows in CI.
- The Windows tests step of the pull request's own CI takes at most 60 % of 949 s (under 570 s), measured on that run and recorded in the ADR with the Linux and macOS steps.
- A test named `test_c9_project_template_*` shows that two tests' projects are separate repositories (a commit or push in one is not seen in the other) and that each one's `origin` is its own remote.
- All checks in CLAUDE.md pass.

## Acceptance checklist

- [ ] `--durations=30` in the `Tests` step of `ci.yml` (applied by the owner from their machine, from the YAML in the ADR: a cloud session cannot push workflow files).
- [ ] The `project` fixture copies a per-worker template; `test_c9_project_template_*` passes.
- [ ] The five slowest avoidable git set-ups on Windows changed, named in the ADR.
- [ ] Windows sharded only if its tests step is still above 8 minutes, with the new required check names in the ADR (the owner updates the ruleset and commits the workflow).
- [ ] A new ADR with the durations before and after.
- [ ] All checks in CLAUDE.md pass.
- [ ] Definition of done, documentation (C25): README's development section if the way to run the tests changes; `docs/architecture/` only if a module of `src/` changes.

## Out of scope

- Changing what any test asserts, or removing tests.
- Runner settings (antivirus exclusions, a Dev Drive): later, if the measurements point there.
- Sharding Linux or macOS.
- Selective checks (#184) and parallel replay inside Ariane (#143).

## Related

#187 and ADR 0048 (parallel tests, four CI jobs), #184, #143; spec C9.


---
_Generated by [Claude Code](https://claude.ai/code)_
