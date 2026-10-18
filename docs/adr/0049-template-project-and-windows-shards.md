# 0049. A template project per worker, and Windows tests in two shards

- Status: accepted
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
all from Ariane itself. The implementer's sandbox cannot run Windows: the 30 slowest on Windows
come from the CI run of `--durations=30` (see "Handover").

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
- **The next slowest avoidable set-ups.** No single test body has avoidable git set-up of the
  size of the fixtures (the bodies' git calls are what they test), so the five changed are the
  set-ups that commit on a branch through a temporary worktree (four or five processes each).
  They now call `commit_on_branch` in `conftest.py`, one `git fast-import` that adds a commit to
  a branch without checking it out, with the same files, message and identity:
  1. the `project` fixture itself (six processes to none, above);
  2. the `branch` fixture of `tests/test_verify.py` (four to one);
  3. the `hand_branch` fixture of `tests/test_c11_guard_hardening.py` (four to one);
  4. the `hand_branch` fixture of `tests/test_c11_remote_scope.py` (four to one);
  5. the racing commit of `test_c23_verify_records_a_branch_committed_to_during_the_run_commits_nothing`
     and `test_c23_verify_records_branch_moved_is_caught_before_the_commit`, and the symbolic
     link commit of `test_c11_guard_hardening_verify_records_replace_a_symlinked_checks_file`
     (four or five to one).
  No assertion changed. With them, the suite starts 18,924 git processes instead of 20,638, 47
  of them in set-up instead of 1,796, and the summed set-up phase on Linux falls from 17.0 s to
  4.7 s (same machine, back to back).
- **Shards on Windows, two.** The set-up phase is about 3 % of the summed test time; even if
  Windows saved twice that share, its tests step would stay far above 8 minutes, so the
  Windows job is split. A `shard` matrix dimension exists on `windows-latest` only, with 2
  shards; Linux and macOS keep one job each. Each shard runs one group of `pytest-split`
  (`--splits 2 --group N --splitting-algorithm least_duration`), a dev dependency, from the
  stored durations in `.test_durations` at the repository root. `pytest-split` was chosen over a
  hand-written split by test file because the work is concentrated in a few files
  (`test_flow.py`, `test_flow_guards.py`, `test_c23_restart.py`, ...), so a per-file split
  balances poorly, while per-test durations balance well and the plugin is small, deterministic
  (the same groups for the same collected tests and durations file) and works under xdist (each
  worker deselects the same tests). A test not in `.test_durations` counts with the average
  duration, so new tests still land in exactly one group
  (`test_c9_shards_two_groups_split_the_whole_suite_from_the_stored_durations`). Two shards
  should take each Windows tests step to about half of its unsharded time, under the 570 s
  target; if the measured shard steps stay above 570 s, a third shard is added (`--splits 3`,
  a third `include` entry, a third required check), as few as reach the target.

The workflow files cannot be pushed from a cloud session (CLAUDE.md, "Cloud sessions"). The
owner applies the change from their machine, in two commits so that each step is measured.

**Commit 1, measure without shards.** In `.github/workflows/ci.yml`, the `Tests` step becomes:

```yaml
      - name: Tests
        if: steps.docs.outputs.docs_only != 'true'
        run: uv run pytest --durations=30
```

**Commit 2, Windows in two shards.** In `.github/workflows/ci.yml`, the job's `name` and
`strategy`, and the `Tests` step, become:

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
check of the system apart from the half of the tests it skips.

## Durations

| Where | Before | After template and set-ups | After 2 Windows shards |
| --- | --- | --- | --- |
| Linux sandbox, 4 CPUs, git processes | 20,638 | 18,924 | (unchanged) |
| Linux sandbox, summed set-up phase | 17.0 s | 4.7 s | (unchanged) |
| Linux CI, tests step (3.13 / 3.11) | 123 s / 124 s (#205) | owner, commit 1 run | owner, commit 2 run |
| macOS CI, tests step | 242 s (#205) | owner, commit 1 run | owner, commit 2 run |
| Windows CI, tests step | 949 s (#205) | owner, commit 1 run | owner, commit 2 run (per shard) |
| Windows CI, job | 16.3 min (#205) | owner, commit 1 run | owner, commit 2 run (per shard) |

Wall time in the implementer's sandbox is not a usable measure: the same suite took 100 to
150 s from run to run, with the change or without it, because of the sandbox's load. The CI
figures are the reference.

## Required checks
ADR 0048 has the ruleset require four CI job names. With commit 2, CI reports five:

- `ubuntu-latest / Python 3.11`
- `ubuntu-latest / Python 3.13`
- `macos-latest / Python 3.13`
- `windows-latest / Python 3.13 / shard 1`
- `windows-latest / Python 3.13 / shard 2`

`windows-latest / Python 3.13` is no longer reported: if the ruleset still requires it, every
pull request waits for it forever. The ruleset changes together with commit 2 and requires
exactly these five names; the `ariane/<check>` statuses of `check-statuses.yml` stay as they
are.

## Handover
The owner, from their machine, on this pull request's branch:

1. Before anything else, takes the Windows "before" list: the 30 slowest tests on Windows from
   a CI run of `main` with `--durations=30` (for example a throwaway branch from `main` with
   only commit 1's change), and adds them here with the Linux list above.
2. Applies commit 1, pushes, waits for the run, and records in the Durations table the tests
   step and job duration of each job, with the 30 slowest Windows tests after the change.
3. If the Windows tests step of that run is at most 480 s (8 minutes), stops here: it writes in
   this ADR that the target is met without shards, and the `pytest-split` dev dependency, the
   `.test_durations` file and the shard test are removed in a follow-up ticket. Otherwise:
4. Opens the repository's ruleset for `main` (Settings, Rules, Rulesets), replaces
   `windows-latest / Python 3.13` by the two shard names listed under "Required checks", then
   applies commit 2 and pushes.
5. Waits for that run: the five jobs pass, no required check stays "expected", and each Windows
   shard's tests step is under 570 s; records the steps and the run's URL in the Durations
   table. If a shard is above 570 s, applies the third shard described above.

## Consequences
Each test that uses `project` starts no git process to get it, on every system, in CI, in
Ariane's replay and on the owner's machine; most of the gain is on Windows. A new fixture that
needs a commit on another branch uses `commit_on_branch` rather than a temporary worktree. The
template is shared within a worker: a test must never write to `project_template`, only copy
it. With shards, CI reports five jobs and the longest Windows job is about half as long; the
durations file grows stale as tests are added, which only unbalances the shards (new tests count
with the average), and is refreshed with `uv run pytest --store-durations`. Ariane's own replay
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
