# 0047. Parallel tests and a smaller CI matrix

- Status: accepted
- Date: 2026-10-18
- Capabilities: C9

## Context
Every pull request waited about 30 minutes for CI. `ci.yml` ran 6 jobs (Linux, macOS and
Windows, each with Python 3.11 and 3.13). The tests took about 4 minutes on Linux and 23 to 26
minutes on Windows (1,375 to 1,611 s on pull requests #171 to #183). No single test dominates
(the slowest takes 7 s): the time is spread over about 690 tests that each start git and other
processes, which is slow on Windows. Ariane replays the same suite on every ticket (C9), and
`check-statuses.yml` replays it again. CLAUDE.md rule 6 asks for the checks on Windows, macOS
and Linux; it does not say with which Python versions or how the tests are scheduled. The owner
decided to run the tests in parallel everywhere and to keep Python 3.11 on Linux only.

## Decision
- **Parallel tests by default.** `pytest-xdist` is a dev dependency and
  `[tool.pytest.ini_options]` has `addopts = "-n auto"`, so `uv run pytest` runs one worker per
  CPU in CI, in Ariane's replay and locally. The check commands in CLAUDE.md and `ariane.toml`
  do not change. `uv run pytest -n 0` runs serially (to debug with `pdb`, for example).
- **No test is grouped.** Every test passes under `-n auto` as it is: each one already uses
  per-test state (`tmp_path`, `monkeypatch`, its own git repositories and bare remotes, an
  isolated git configuration from `conftest.py`). Nothing uses a fixed port or a shared path.
  The tests that rely on the process tree of the pytest process (the subreaper and survivor
  tests of C10) see only their own worker's tree: each xdist worker is a separate process, the
  subreaper flag is per process, `kill_survivors` follows only the descendants of the calling
  process and never signals its own process group or session, and the Windows tree kill
  (`taskkill /T /PID`) targets one child. No test is marked `xdist_group`, and the suite runs
  with the default distribution, not `--dist loadgroup`.
- **Matrix.** Python 3.13 on `ubuntu-latest`, `macos-latest` and `windows-latest`, plus
  Python 3.11, the minimum of `requires-python`, on `ubuntu-latest` only: 4 jobs instead of 6.
  Rule 6 still holds. Differences between 3.11 and 3.13 are in the language and standard
  library, which a Linux job covers; differences between systems are covered with 3.13.
- **Cache.** `astral-sh/setup-uv` runs with `enable-cache: true` in both workflows.

The workflow files cannot be pushed from a cloud session (CLAUDE.md, "Cloud sessions"). The
owner applies these two changes from their machine, in the same pull request.

In `.github/workflows/ci.yml`, the `strategy` and the `setup-uv` step become:

```yaml
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
        python: ["3.13"]
        include:
          - os: ubuntu-latest
            python: "3.11"
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: astral-sh/setup-uv@v6
        with:
          python-version: ${{ matrix.python }}
          enable-cache: true
```

In `.github/workflows/check-statuses.yml`, the `setup-uv` step becomes:

```yaml
      - uses: astral-sh/setup-uv@v6
        with:
          enable-cache: true
```

## Durations

| Where | Before (serial) | After (`-n auto`) |
| --- | --- | --- |
| Linux, 4 CPUs (implementer's sandbox, 691 tests) | 385 s | 102 s |
| Linux CI job, tests step | about 4 min | to measure on this pull request's CI |
| Windows CI job, tests step | 1,375 to 1,611 s (about 26 min for the job) | to measure on this pull request's CI |
| macOS CI job, tests step | not measured | to measure on this pull request's CI |
| Longest CI job of a pull request | about 30 min | target: under 12 min; to measure on this pull request's CI |
| CI run of this pull request | | URL to record |

The "after" CI cells cannot be measured by the implementer: the workflow changes are applied by
the owner (below), and only then does this pull request's CI run with them. They stay open until
that run, and the pull request is not merged before they are filled in (handover step 5).

## Required checks
ADR 0005 has the repository ruleset require the six CI job names. The job name is
`${{ matrix.os }} / Python ${{ matrix.python }}`, so after this change CI reports only four:

- `ubuntu-latest / Python 3.11`
- `ubuntu-latest / Python 3.13`
- `macos-latest / Python 3.13`
- `windows-latest / Python 3.13`

`macos-latest / Python 3.11` and `windows-latest / Python 3.11` are no longer reported. If the
ruleset still requires them, every pull request waits for them forever and cannot be merged. The
ruleset therefore changes together with the workflow: it requires exactly the four names above,
and the `ariane/<check>` statuses of `check-statuses.yml` stay as they are.

## Handover
The owner, from their machine, on this pull request's branch:

1. Applies the two YAML changes above to `.github/workflows/ci.yml` and
   `.github/workflows/check-statuses.yml`, then commits and pushes them.
2. Opens the repository's ruleset for `main` (Settings, Rules, Rulesets) and checks the list of
   required status checks it actually has, since it may differ from ADR 0005.
3. Removes `macos-latest / Python 3.11` and `windows-latest / Python 3.11` from the required
   checks, and keeps (or adds) the four names listed under "Required checks". No other required
   check is changed.
4. Waits for this pull request's CI: the four jobs pass (so `-n auto` passes on Linux, macOS and
   Windows), and no required check stays "expected" or "waiting".
5. Records, in the Durations table, the tests step and total duration of each of the four jobs
   and the run's URL, from that run; the longest job must be under 12 minutes. If it is not,
   the pull request is not merged and the decision is revisited.

## Consequences
The tests take about a quarter of the time on a 4-CPU machine, in CI, in Ariane's replay and on
the owner's machine, and a pull request waits for 4 jobs instead of 6. A new test must not use
shared state (a fixed port, a fixed path outside `tmp_path`, a global another test changes): it
can run at the same time as any other test. If one cannot avoid it, it is marked
`@pytest.mark.xdist_group`, the suite gets `--dist loadgroup`, and this ADR is superseded naming
the test. A failure seen only with Python 3.11 on macOS or Windows would no longer be caught by
CI. The output of a failing test is shown by its worker, and `-n 0` gives the serial order back.

## Alternatives considered
- Keep 6 jobs and only parallelise: the Python 3.11 jobs on macOS and Windows find nothing the
  others do not, and each Windows job is the slowest of the run.
- Drop Python 3.11 from CI entirely: `requires-python` promises 3.11, so it must be tested
  somewhere.
- Parallelise only in CI (`-n auto` in the workflow command): Ariane's replay and the owner's
  machine would stay serial, and CI would no longer run the command CLAUDE.md lists.
- Split the suite into CI shards: more jobs, more setup time per job, and Ariane's replay would
  not gain anything.
