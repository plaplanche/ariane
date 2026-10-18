# 0049. A template project per worker, and Windows shards only if still above 8 minutes

- Status: accepted; the Windows job runs in two shards (measured on this pull request's CI,
  see "Durations")
- Date: 2026-10-18
- Capabilities: C9

## Context
After ADR 0048 the tests run in parallel and CI runs four jobs, but Windows stays by far the
longest: on pull request #205 the tests step took 949 s on `windows-latest`, against 123 s on
`ubuntu-latest` and 242 s on `macos-latest`, with the same `-n auto` (16.3 minutes for the
Windows job). The owner accepted it for then and asked for faster Windows tests later. The
suite computes little: most tests build git repositories and start processes, and starting a
process costs far more on Windows than on Linux. Every pull request waits for that job, and
Ariane replays the same suite on the owner's Windows machine (C9, CLAUDE.md rule 6). Issue #206
asks to measure first, to copy a template project instead of rebuilding it for every test, to
cut the next slowest avoidable git set-ups, and to shard the Windows job only if its tests step
stays above 8 minutes; the target is a Windows tests step under 570 s (60 % of 949 s).

## Measurements before the change
Counted with a `git` wrapper first on `PATH` that logs each call with `PYTEST_CURRENT_TEST`
(Linux, 4 CPUs, `-n auto`, 714 tests):

- 20,638 git processes in the whole suite: 1,796 in fixture set-up (the `project` fixture's six
  calls, 284 times, and the hand-branch fixtures' four calls, 23 times), the rest in test bodies,
  almost all of them Ariane's own git calls in the flow under test.
- Summed over the workers, the set-up phase took 17.0 s and the test bodies 467 s.

The 30 slowest on Linux before the change (`--durations=30`; seconds, test body): 7.01
`test_process_timeout_kills_the_whole_tree`, 6.08 `test_c5_idle_stream_a_command_printing_every_second_is_not_killed`,
4.77 `test_c23_restart_another_ticket_restarting_meanwhile_does_not_stop_this_one`, 4.16
`test_c11_parallel_guard_a_whole_second_run_during_the_session_does_not_stop_the_first`, 3.79
`test_c9_isolated_replay_no_tree_is_left_after_green_failing_or_stopped`, 3.54
`test_c5_idle_stream_kills_a_silent_command_and_its_whole_tree`, 3.31
`test_c1_delivery_record_draft_status_says_needs_a_human_before_and_after`, 3.15
`test_c1_delivery_record_statuses_stay_on_the_pushed_commit[draft]`, 3.13
`test_c26_dod_review_an_item_answered_unmet_makes_the_review_no_go`, 3.12
`test_c1_delivery_record_is_one_local_commit_on_the_ticket_folder_after_the_push[draft]`, 3.12
`test_c10_small_review_small_model_gets_its_own_provider_login`, 3.09
`test_c26_dod_review_an_item_missing_from_the_answer_makes_the_review_no_go`, 3.09
`test_c10_fix_round_three_no_go_give_a_draft_pull_request_with_the_findings`, 3.08
`test_process_background_children_do_not_outlive_a_normal_exit`, 3.06
`test_c10_review_go_with_a_blocking_finding_is_no_go_and_goes_to_fix_rounds`, 3.04
`test_c1_delivery_record_leaves_the_ticket_working_tree_clean[draft]`, 2.81
`test_c5_idle_opencode_reviewer_stops_with_timeout_and_the_summary_in_the_journal`, 2.78
`test_c10_fix_round_blocking_checks_failing_after_a_fix_round_count_as_negative`, 2.62
`test_c23_restart_a_tree_left_during_the_run_names_restart_once`, 2.55
`test_c23_restart_after_a_stop_start_refuses_and_restart_keeps_the_branch_and_delivers`, 2.42
`test_c9_isolated_replay_setup_runs_once_per_check`, 2.40
`test_c21_role_env_the_fix_session_does_not_hold_the_reviewers_key`, 2.40
`test_c19_metrics_fix_round_counts_rounds_and_keeps_the_first_pass_no_go`, 2.39
`test_c10_unchanged_fix_after_red_checks_gives_the_draft_without_a_second_replay`, 2.38
`test_c23_restart_keeps_the_work_of_an_interrupted_session`, 2.37
`test_c10_unchanged_fix_a_session_that_commits_by_itself_is_not_unchanged`, 2.34
`test_c19_metrics_blocking_red_at_delivery_is_recorded`, 2.34
`test_c10_fix_round_the_fix_session_receives_the_findings_as_data`, 2.34
`test_c10_fix_round_no_go_then_go_delivers_a_normal_pull_request`, 2.29
`test_c10_survivor_groups_a_process_that_keeps_forking_is_killed_20_times_in_a_row`.

The slowest tests are whole Ariane runs (start, replay, review, fix rounds, delivery) and the
process-tree tests that wait on purpose; each runs 100 to 190 git processes in its body, nearly
all from Ariane itself.

**The 30 slowest on Windows, after the change** (CI run of commit 1, `windows-latest / Python
3.13`, seconds, test body): 48.7 `test_fix_rounds` three no-go rounds, 40.4 `test_c9_isolated_replay`
no tree left, 38.2, 37.7 and 37.6 three `test_review` runs to fix rounds, 37.0 `test_c23_restart`
another ticket restarting, 36.1 to 33.8 four `test_c1_delivery_record` draft deliveries, 33.6
`test_fix_rounds` red checks after a fix round, 33.3 `test_c11_parallel_guard` a second run, 33.0
`test_c10_small_review`, then 32.0 down to 22.4 for sixteen more whole runs (`test_fix_rounds`,
`test_c23_restart`, `test_c9_isolated_replay`, `test_c19_metrics`, `test_flow`, `test_c5_opencode`,
`test_flow_setup_env`). Every one of them is a whole Ariane run (start, replay in fresh trees,
review, fix rounds, delivery), the same family as the Linux list, about 7 times slower: none is a
fixture set-up of avoidable git processes outside the five of "Decision", so the set-ups chosen
from the Linux list stand. The "before" list on Windows was not taken (step 1 of "Handover"):
the after list shows where the time goes, and it is in Ariane's own git and process work during
a run, not in the tests' set-up. Making those runs cheaper in tests is a separate ticket.

## Decision
- **Measure in CI.** The `Tests` step of `ci.yml` runs `uv run pytest --durations=30` on every
  job. The command CLAUDE.md lists stays `uv run pytest`; `--durations` only adds the report.
- **A template project per worker.** `tests/conftest.py` has a session-scoped
  `project_template` fixture that builds the bare remote and its clone once per xdist worker,
  under the worker's base temp directory, with the six git calls the `project` fixture used to
  run per test. `project` now copies both directories into the test's `tmp_path`
  (`shutil.copytree`, `copy_template`) and rewrites the single `url =` line of the copy's
  `.git/config` to the test's own remote, quoted as git quotes a value: no git process per test.
  What a test sees does not change: `Project.root` (resolved) and `Project.remote` under its
  `tmp_path`, branch `main` checked out, one commit `initial` by the test identity, `app.txt`
  and `.gitignore`, a clean tree, `origin` pointing at its own remote. The template sets its own
  isolated git configuration and identity, since a session fixture runs before the per-test
  `isolated_git`.
- **Why the copy is safe under xdist.** Each worker is a separate process with its own base
  temp directory (`popen-gwN`), so each builds its own template; the template is never given to
  a test, only copied, and nothing writes to it after it is built. Each test gets its own
  repository and remote: a commit or push in one copy is not seen in another, and each copy's
  `origin` is its own remote (`tests/test_c9_project_template.py`). The copies share their
  initial commit id within a worker, which no test relies on being different. Serially
  (`-n 0`) there is one template for the session.
- **The next slowest avoidable set-ups.** Beyond the `project` fixture, five more set-ups are
  changed. They are chosen, for now, from the Linux count of git processes per test above,
  since no Windows list exists yet: a set-up that starts git processes costs more on Windows
  than on Linux, never less, so the set-ups with the most of them are the first candidates on
  both. This choice is provisional: it is checked against the Windows list of "Handover",
  step 1, and if that list shows a slow test whose set-up starts avoidable git processes and is
  not below, it replaces the least of the five in a fix round of this ticket, not in a
  follow-up. No single test body has avoidable git set-up of the size of the fixtures (the
  bodies' git calls are what they test). The five commit on a branch through a temporary
  worktree or another clone (four or five processes each); they now call `commit_on_branch` in
  `conftest.py`, one `git fast-import` that adds a commit to a branch without checking it out,
  with the same files, message and identity:
  1. the `branch` fixture of `tests/test_verify.py` (four to one);
  2. the `hand_branch` fixture of `tests/test_c11_guard_hardening.py` (four to one);
  3. the `hand_branch` fixture of `tests/test_c11_remote_scope.py` (four to one);
  4. the racing commit of `test_c23_verify_records_a_branch_committed_to_during_the_run_commits_nothing`
     and `test_c23_verify_records_branch_moved_is_caught_before_the_commit`, and the symbolic
     link commit of `test_c11_guard_hardening_verify_records_replace_a_symlinked_checks_file`
     (four or five to one);
  5. the fast-forward of the base branch by another party, in
     `test_c11_remote_check_a_fast_forward_of_the_base_branch_does_not_stop` and the
     non-rewriting `_advance_base` of `tests/test_c11_remote_scope.py`: a clone, `add`,
     `commit` and `push` become one `commit_on_branch` straight into the bare remote (four to
     one). The rewriting variant keeps its clone: it replaces the root commit, which
     `commit_on_branch` does not do.
  No assertion changed. With the template and items 1 to 4, the suite starts 18,924 git
  processes instead of 20,638, 47 of them in set-up instead of 1,796, and the summed set-up
  phase on Linux falls from 17.0 s to 4.7 s (same machine, back to back); item 5 saves about
  three more processes in each of its three tests.
- **Regression checks.** `tests/test_c9_project_template.py` runs a two-test suite in a child
  pytest and finds a single `project-template` directory under its base temp (one template per
  session, two projects), and gets a `project` while starting a process is refused (the copy
  starts no process); both fail if the template is rebuilt per test or the copy calls git.
- **Shards on Windows, only if the measurement asks for it.** Not decided by this ADR's
  author: the order is measure, then shard. The Windows tests step of the run of commit 1
  below (template and set-ups, no shards) decides. If it is at most 480 s (8 minutes), nothing
  is sharded, and this ADR records the figure and says so. If it is above, the Windows job is
  split into two shards, and into three only if a shard's tests step is then above 570 s, as
  few as reach the target. The sandbox's Linux figures do not decide it: they say nothing of
  Windows' cost per process, which is what #205's 949 s measures.
- **How Windows would be sharded.** A `shard` matrix dimension on `windows-latest` only; Linux
  and macOS keep one job each. Each shard runs one group of `pytest-split`
  (`--splits 2 --group N --splitting-algorithm least_duration`), a dev dependency, from the
  stored durations in `.test_durations` at the repository root. Both are in this pull request,
  so that commit 2 is a workflow change only; they change nothing for `uv run pytest`, which
  runs the whole suite as before. `pytest-split` was chosen over a hand-written split by test
  file because the work is concentrated in a few files (`test_flow.py`, `test_flow_guards.py`,
  `test_c23_restart.py`, ...), so a per-file split balances poorly, while per-test durations
  balance well and the plugin is small, deterministic (the same groups for the same collected
  tests and durations file) and works under xdist (each worker deselects the same tests). A
  test not in `.test_durations` counts with the average duration, so new tests still land in
  exactly one group (`test_c9_shards_two_groups_split_the_whole_suite_from_the_stored_durations`).
  If the measurement says no shards, the dependency, the durations file and that test are
  removed in a follow-up ticket.
- **The suite ran serially in CI once, on this pull request.** A `serial` job ran
  `uv run pytest -n 0` with Python 3.13 on Linux, macOS and Windows, so that a test passing only
  under xdist (or only serially) would show: all three passed (see "Durations"). The owner
  decided (18 October 2026) to keep it for this pull request only: serially, Windows takes about
  29 minutes, and a job nobody may merge past while it is red is a job everyone waits for.
  Commit 2 removes it; a serial run after the merge belongs to the CI stages of #208.

The workflow files cannot be pushed from a cloud session (CLAUDE.md, "Cloud sessions"). The
owner applies the change from their machine, in two commits so that each step is measured.

**Commit 1, measure, without shards, with the serial job.** In `.github/workflows/ci.yml`, the
`Tests` step of the `checks` job becomes:

```yaml
      - name: Tests
        if: steps.docs.outputs.docs_only != 'true'
        run: uv run pytest --durations=30
```

and a second job is added under `jobs:`, after `checks`:

```yaml
  serial:
    name: ${{ matrix.os }} / serial
    runs-on: ${{ matrix.os }}
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: astral-sh/setup-uv@v6
        with:
          python-version: "3.13"
          enable-cache: true
      - name: Detect documentation-only pull request
        id: docs
        shell: bash
        env:
          EVENT: ${{ github.event_name }}
          BASE: ${{ github.event.pull_request.base.sha }}
          HEAD: ${{ github.event.pull_request.head.sha }}
        run: |
          if [ "$EVENT" = "pull_request" ]; then
            git diff --name-only --no-renames "$BASE" "$HEAD" | uv run --no-project python scripts/docs_only.py >> "$GITHUB_OUTPUT"
          else
            echo "docs_only=false" >> "$GITHUB_OUTPUT"
          fi
      - name: Install
        if: steps.docs.outputs.docs_only != 'true'
        run: uv sync --locked
      - name: Tests, serial
        if: steps.docs.outputs.docs_only != 'true'
        run: uv run pytest -n 0 --durations=30
```

**Commit 2, only if commit 1's Windows tests step is above 480 s: Windows in two shards.** In
`.github/workflows/ci.yml`, the `checks` job's `name` and `strategy`, and its `Tests` step,
become:

```yaml
  checks:
    name: ${{ matrix.os }} / Python ${{ matrix.python }}${{ matrix.shard && format(' / shard {0}', matrix.shard) || '' }}
    runs-on: ${{ matrix.os }}
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, macos-latest]
        python: ["3.13"]
        include:
          - os: ubuntu-latest
            python: "3.11"
          - os: windows-latest
            python: "3.13"
            shard: 1
          - os: windows-latest
            python: "3.13"
            shard: 2
```

```yaml
      - name: Tests
        if: steps.docs.outputs.docs_only != 'true'
        run: uv run pytest --durations=30 ${{ matrix.shard && format('--splits 2 --group {0} --splitting-algorithm least_duration', matrix.shard) || '' }}
```

The other steps (install, lint, format, types, file length, the two PowerShell smoke tests) run
in both Windows shards unchanged: they take seconds, and each Windows job stays a complete
check of the system apart from the half of the tests it skips. The same commit removes the
`serial` job.
In the same commit, the last sentence of README's "Develop Ariane" section says that Windows
CI runs the tests in two shards, `uv run pytest --splits 2 --group 1` (or `2`) with
`--splitting-algorithm least_duration`, balanced from `.test_durations`.

## Durations

"Pending" is a figure no run has produced yet; the owner fills it in from the runs of
"Handover", with each run's URL. Until every pending cell of the first two columns is filled,
the acceptance criteria on CI durations and on the serial suite are not shown.

| Where | Before | After template and set-ups (commit 1) | After Windows shards (commit 2, if any) |
| --- | --- | --- | --- |
| Linux sandbox, 4 CPUs, git processes | 20,638 | 18,924 | (unchanged) |
| Linux sandbox, summed set-up phase | 17.0 s | 4.7 s | (unchanged) |
| Linux sandbox, `uv run pytest -n 0` | (not run) | 720 passed, 2 skipped, 400 s | (unchanged) |
| Linux CI, tests step (3.13 / 3.11) | 123 s / 124 s (#205) | 125 s / 95 s | 106 s / 98 s |
| macOS CI, tests step | 242 s (#205) | 217 s | 175 s |
| Windows CI, tests step | 949 s (#205) | 905 s (869 s on the run before commit 1) | 369 s / 305 s (shard 1 / 2) |
| Windows CI, job | 16.3 min (#205) | 15 min | 6.6 min / 5.7 min |
| Serial job, Linux / macOS / Windows | (no such job) | passed: 276 s / 473 s / 1,755 s | removed |
| Run URL | #205 | https://github.com/plaplanche/ariane/actions/runs/39153818737 | https://github.com/plaplanche/ariane/actions/runs/39162324189 |

Wall time in the implementer's sandbox is not a usable measure: the same suite took 100 to
150 s from run to run, with the change or without it, because of the sandbox's load. The CI
figures are the reference.

## Required checks
ADR 0048 has the ruleset require four CI job names. Commit 1 changes none of them: the `serial`
jobs (`ubuntu-latest / serial`, `macos-latest / serial`, `windows-latest / serial`) are reported
but not required. Only if commit 2 is applied, CI reports five required jobs:

- `ubuntu-latest / Python 3.11`
- `ubuntu-latest / Python 3.13`
- `macos-latest / Python 3.13`
- `windows-latest / Python 3.13 / shard 1`
- `windows-latest / Python 3.13 / shard 2`

`windows-latest / Python 3.13` is then no longer reported: if the ruleset still requires it,
every pull request waits for it forever. The ruleset changes together with commit 2 and
requires exactly these five names; the `ariane/<check>` statuses of `check-statuses.yml` stay as
they are. Without commit 2, the ruleset does not change.

## Handover
This ticket is not done until the owner has run these steps and recorded their figures here:
an implementer can neither run Windows nor push a workflow file. The owner, from their machine,
on this pull request's branch:

1. Takes the Windows "before" list: the 30 slowest tests on Windows from a CI run of `main` with
   `--durations=30` (for example a throwaway branch from `main` with only the `Tests` step of
   commit 1), and adds it under "Measurements before the change", beside the Linux list. If it
   names a slow test whose set-up starts avoidable git processes and is not among the five of
   "Decision", the pull request goes back to a fix round with that list as a finding.
2. Applies commit 1, pushes, waits for the run, and records in the Durations table the tests
   step and job duration of each `checks` job, the result and step duration of each `serial`
   job, the run's URL, and the 30 slowest Windows tests after the change. The three `serial`
   jobs pass; if one fails, the pull request goes back to a fix round.
3. If the Windows tests step of that run is at most 480 s (8 minutes), stops here: it writes in
   "Decision" that the target is met without shards, and the `pytest-split` dev dependency, the
   `.test_durations` file and the shard test are removed in a follow-up ticket. Otherwise:
4. Opens the repository's ruleset for `main` (Settings, Rules, Rulesets), replaces
   `windows-latest / Python 3.13` by the two shard names listed under "Required checks", then
   applies commit 2 (with its README sentence) and pushes.
5. Waits for that run: every job passes, no required check stays "expected", and each Windows
   shard's tests step is under 570 s; records the steps and the run's URL in the Durations
   table. If a shard is above 570 s, applies a third shard (`--splits 3`, a third `include`
   entry, a third required check).

## Consequences
Each test that uses `project` starts no git process to get it, on every system, in CI, in
Ariane's replay and on the owner's machine; most of the gain is on Windows. A new fixture that
needs a commit on another branch uses `commit_on_branch` rather than a temporary worktree. The
template is shared within a worker: a test must never write to `project_template`, only copy
it. The suite ran serially on the three systems once, on this pull request, and passed; no CI job
runs it serially any more (after the merge, #208). With
shards, CI reports five required jobs and the longest job of a pull request went from 15 to 6.6
minutes; the durations file grows stale as tests are added, which only
unbalances the shards (new tests count with the average), and is refreshed with
`uv run pytest --store-durations`. Ariane's own replay
does not shard: it runs `uv run pytest` as before.

## Alternatives considered
- `git remote set-url` in each copy: one git process per test, where rewriting the one `url =`
  line of a file just copied costs none.
- A template with `git clone --local` or worktrees per test: still several git processes per
  test, and a worktree shares the object store and refs with the template, so a test could see
  another's commits.
- A split by test file, without a new dependency: a few files hold most of the time, so two
  groups by file differ by much more than two groups by test.
- Three shards from the start: more jobs and setup time for a target two should reach; added
  only if the measurement says so.
- Runner settings (antivirus exclusions, a Dev Drive): out of scope of #206, later if the
  measurements point there.
