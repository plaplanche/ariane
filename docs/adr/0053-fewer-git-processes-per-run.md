# 0053. Fewer git processes per run: one read of git per verification, one diff per review, one process for a detached head, three processes per record commit

- Status: accepted. The issue's Windows target (60 % of ADR 0049) is missed at 69 %; the owner
  accepted the measured result on 19 October 2026 and moved the target to #221 (see "Durations")
- Date: 2026-10-19
- Capabilities: C9, C11

## Context
ADR 0049 found that the 30 slowest tests on Windows (22 to 49 s each on `windows-latest`, about
7 times their Linux time) are all whole Ariane runs driven by a fake runtime. Their cost is
Ariane's own git work during a run, not the tests' set-up. The same work runs in real tickets,
where it adds seconds per round, most on Windows, where starting a process costs most. Issue #214
asks to measure by phase first, then to cut the three costliest phases without weakening any
guarantee: the push guard compares the same things (ADR 0017) and each check is still replayed
in its own clean tree (C9, ADR 0041). No test may be removed, skipped or made to assert less.
Target: the sum of the 30 slowest Windows tests drops by at least 40 % against ADR 0049's figures.

## Measurements
`tests/process_phases.py` counts the processes Ariane starts through `process.run` during a
block, by phase, and the wall time spent inside them. A call's phase is set by the innermost
frame of Ariane's code that names one (for example `flow._TicketRun.verify` for guard
verification, `git.remote_refs` for remote listing, `flow._TicketRun._commit_record` for record
commits). A call that no such frame names (preparing the tree, opening the ticket folder, reading
the head) counts as setup. Counted on Linux (the sandbox, serially, `uv run pytest -s -n 0 -k
c11_fewer_processes`), on the code before this change (`HEAD` of `main` when #214 opened) and
after, with the same counter. Each cell is processes (seconds inside them):

| Run | setup | session | guard verification | remote listing | replay | review | record commits | delivery | total |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Go on the first round, before | 11 (0.12) | 7 (0.16) | 46 (0.34) | 5 (0.06) | 3 (0.06) | 6 (0.06) | 12 (0.54) | 3 (0.12) | 93 (1.46) |
| Go on the first round, after | 11 (0.15) | 6 (0.18) | 23 (0.16) | 5 (0.08) | 3 (0.07) | 4 (0.06) | 9 (0.43) | 3 (0.08) | 64 (1.21) |
| Three no-go rounds to a draft, before | 13 (0.16) | 29 (0.58) | 108 (0.80) | 11 (0.15) | 9 (0.19) | 18 (0.20) | 12 (0.46) | 3 (0.08) | 203 (2.62) |
| Three no-go rounds to a draft, after | 13 (0.13) | 26 (0.54) | 53 (0.39) | 11 (0.14) | 9 (0.20) | 12 (0.16) | 9 (0.44) | 3 (0.09) | 136 (2.09) |
| Restart after a stop, before | 29 (0.26) | 7 (0.17) | 46 (0.33) | 5 (0.06) | 3 (0.07) | 6 (0.06) | 12 (0.45) | 3 (0.05) | 111 (1.45) |
| Restart after a stop, after | 29 (0.27) | 6 (0.16) | 23 (0.16) | 5 (0.06) | 3 (0.07) | 4 (0.07) | 9 (0.41) | 3 (0.05) | 82 (1.25) |
| Go with three checks, before | 11 (0.12) | 7 (0.17) | 68 (0.52) | 7 (0.10) | 9 (0.21) | 6 (0.06) | 12 (0.43) | 3 (0.05) | 123 (1.66) |
| Go with three checks, after | 11 (0.11) | 6 (0.17) | 33 (0.22) | 7 (0.09) | 9 (0.22) | 4 (0.04) | 9 (0.42) | 3 (0.09) | 82 (1.36) |

The times are one serial run each; they vary by about 20 % from run to run. In the sandbox every
`git commit` takes about 0.12 s, because the sandbox's own git configuration signs commits with an
external program; that is why the record commits (three commits) weigh so much in time there.
CI does not sign commits, so there a commit costs about what any git process costs.

Before the change, guard verification was by far the costliest phase: about half of every run's
processes. Each verification started ten git processes: `rev-parse` twice for the git folders,
`git config --file -` for the shared config's keys, `git config --list --show-origin
--show-scope`, `for-each-ref`, `rev-parse --verify` for the base's tracking ref, then
`symbolic-ref` for the branch, `merge-base --is-ancestor`, `rev-parse HEAD` and `ls-remote`.
Summed over the four runs, the phases come next in this order: setup (64), session (50), record
commits (48), review (36), remote listing (28), replay (24).

## Decision
Four phases are cut: guard verification, the session's commit, the record commits and the review.

Setup is the second costliest by count, but each of its processes runs once per run and reads
something different (the remote's URL, the fetch, the base's instruction file, the branch, the
tree); cutting one of them saves one process per run, while each of the cuts below saves one or
more per verification or per commit. The remote listing is not cut (see "Alternatives
considered").

- **One read of git per verification** (`git.state`, three git processes instead of six). It
  runs one `rev-parse --path-format=absolute --git-common-dir --git-dir` for both folders,
  `git config --list --show-origin --show-scope` as before, and one `git for-each-ref
  --format=%(refname) %(objectname) %(HEAD)` over `refs/heads`, `refs/tags` and the watched refs.
  The files (shared and worktree config, hooks, info) are read and digested directly, as before.
  The shared config's `keys <path>` part now holds the file's text, the very bytes its digest is
  taken from. `runs.foreign_changes` lists both texts with `git config --file - --list --null`
  (`git.config_keys`) only when they differ, then compares them by key exactly as before; when
  they differ but list the same entries (a comment), the `keys` part is dropped and the digest
  change is kept, as before. The watched ref's value is the object `for-each-ref` names, and
  `""` when absent, as `rev-parse --verify` gave. `flow._TicketRun.verify` takes the branch and
  head from the same read (`%(HEAD)`), not from `symbolic-ref` and `rev-parse HEAD`. It still
  checks the branch, the ancestry, the expected head, git and the instruction files, then lists
  the remote, in that order, with the same stops. A verification therefore runs three
  processes, plus `merge-base --is-ancestor`, plus the remote listing.
- **The ancestry every time.** `merge-base --is-ancestor start head` still runs at every
  verification, even for a head already verified. A commit id does not fix git's view of its
  history: the shared `shallow` file and replacement refs (`refs/replace/`) change the ancestry
  git computes, and neither is part of the snapshot. A check could otherwise cut the history
  (write the checked commit to `shallow`) with the verification after it skipping the ancestry,
  and a later check delete the file before anything looked again. An earlier round of this
  change cached the ancestry per head; it was dropped for this reason.
- **One diff per review.** `git.changes` reads the reviewed range once (`git diff --raw
  --numstat -p`) and gives the patch, the `--name-status` listing (the raw lines after their
  modes and objects) and the changed lines (the `--numstat` sum, a binary file counting 0), where
  three `git diff` processes gave them; the review of `ariane start` and of `ariane verify` use
  it. The three are byte for byte what the separate commands printed, with the same pathspec and
  without external diff or textconv drivers.
- **The replay and reviewer trees in one process.** `git.detached_head` (`rev-parse HEAD
  --symbolic-full-name HEAD`) replaces `symbolic-ref` plus `rev-parse HEAD` for a tree that
  must stay detached at the checked commit (`replay`, and the replay tree of `ariane verify`).
- **Three processes per commit.** `git.commit` runs `reset`, `add`, `commit`, and compares the
  index with HEAD (`git diff --cached --quiet`) only when `git commit` refused. If nothing is
  staged it still returns False; any other refusal raises `GitError`. The `reset` first also
  clears a merge state an agent may have left (`MERGE_HEAD`), as before, so a commit without a
  change is never a merge commit. This serves the record commits and the agent session's commit.

What each cut keeps:

- *Guard (ADR 0017):* the parts compared are the same, with the same keys and the same values for
  every part except `keys <path>`, whose value is the text it was parsed from (it changes exactly
  when that text changes). The same parts are tolerated for another run (`runs.foreign_changes`,
  unchanged in what it drops). The shared config's digest and keys still come from one read of
  the file. The reads still happen after the survivors are killed and before the registry is
  read. Every verification still lists the remote, after each check of the replay too, so a
  check that pushes stops the ticket before the next check runs. Every stop the guard raised
  before, it raises now, with the same reason.
- *Review:* the reviewer gets the same diff, the same list of changed files and the same size
  (ADR 0046, ADR 0031).
- *Clean-tree replay (C9, ADR 0041):* unchanged. Each check still gets its own fresh tree,
  created, set up, run, verified (git, its head and the remote) and removed, in the same order.

Regression checks, `tests/test_c11_fewer_processes.py` (`uv run pytest -k c11_fewer_processes`):

- the four runs of the table stay within their "after" counts per phase, and each cut phase
  stays below its "before" count. A later change that raises one fails, and raising a bound
  needs a new decision. With `-s`, each prints its counts and times per phase;
- `git.state` starts three processes, with a branch listed before the checked-out one (the
  `%(HEAD)` mark is read whatever the line), a record commit starts `reset`, `add`,
  `commit`, and `git.changes` starts one process and gives what the three diffs gave (a rename,
  a deletion, a mode change, a binary file, a path with a space, `work/` left out);
- the guard still stops on each tampering: a planted hook, a config key, a comment in the shared
  config, a local branch, a tag, the base's tracking ref, a detached HEAD, a rewritten history
  and a pushed remote branch (after the agent session); a check that pushes a tag to the remote;
  a first check that pushes a tag and a second that deletes it (the first stops the ticket, the
  tag is still there: the second never ran); a second check that writes the checked commit to
  the shared `shallow` file and a third that would delete it (the second stops the ticket as a
  rewritten history, the third never runs); a reviewer that commits on the ticket branch; and, in `ariane verify`, a check that puts the
  replay tree's HEAD back on a branch at the same commit.

The tests that existed are unchanged, with two exceptions.
`test_c11_guard_hardening_verify_refuses_a_check_that_edits_git_config` fails the test if the
review's diff is read after the guard tripped; it now watches `git.changes`, the function that
reads it, and `test_c11_guard_hardening_diffs_ignore_external_and_textconv_drivers` also reads
`git.changes`.
`test_c11_parallel_guard_another_run_writing_during_the_baseline_is_tolerated` used to write
just before the `git config --file -` call. That call no longer runs while the snapshot is taken,
so the test now writes just before the read of the folders, which is followed by the read of the
shared config. Its assertion is the same.

## Durations

| Where | Before (the code of `main` when #214 opened) | This change |
| --- | --- | --- |
| Linux sandbox, git processes of a go run / three no-go rounds / a restart / three checks | 93 / 203 / 111 / 123 | 64 / 136 / 82 / 82 (69 / 67 / 74 / 67 %) |
| Linux sandbox, time inside those processes (table above) | 1.46 / 2.62 / 1.45 / 1.66 s | 1.21 / 2.09 / 1.25 / 1.36 s |
| Linux sandbox, sum of the 30 slowest tests (`--durations=30`, whole suite, `-n auto`) | 118.5 s | 106.8 s |
| Windows CI, sum of the 30 slowest tests | 928.9 s (ADR 0049, run 39153818737, one job); 765.5 s (`main` at a768015, run 39199702035, two shards) | 641.0 s (run 39204844367, two shards): 69 % of ADR 0049, 84 % of `main` |
| Windows CI, tests step per shard | 412 s / 355 s (run 39199702035) | 390 s / 346 s (run 39204844367) |

The exact sum of ADR 0049's thirty Windows figures is 928.9 s (the `--durations=30` report of
run 39153818737, `windows-latest / Python 3.13`, one job of four workers), so the target, 60 %
of it, is 557.3 s. With two shards (ADR 0049, commit 2), each job reports its own thirty slowest;
the figures here are the thirty slowest of both reports merged.

The sandbox's sum of the 30 slowest includes tests that wait on purpose (process trees, idle
limits, parallel checks), which this change does not touch, and its wall time varies from run to
run (ADR 0049), so it says little about Windows.

**The Windows target is missed: 641.0 s, 69 % of ADR 0049's 928.9 s, against at most 60 %.**
The measurement is the pull request's own CI (run 39204844367, both Windows shards). It matches
the prediction from the counts (whole runs start 26 to 33 % fewer git processes, so 67 to 74 %).
Part of the gap to ADR 0049 is not this change: `main` just before it, with the same two shards,
already summed 765.5 s (run 39199702035), and this change takes 16 % off that. The owner
accepted the measured result for #214 on 19 October 2026; reaching 60 % is #221, after #184,
#185 and #209, which cut the number and the cost of the trees a run makes.

What is left to cut without weakening a guarantee is small. A verification is now four git
processes and the remote listing, and each of them reads something the guard needs and no other
process gives (the folders, the configuration with its origins, the refs, the ancestry, the
remote). The session's two diffs read two different ranges (what was committed under `work/`,
what changed in the tree), and its reset, add and commit are what keep a commit from carrying
what an agent staged or a merge it left. Setup reads run once per run. The larger costs left are
the trees themselves: one worktree added and removed per check and per review, with its
checkout, which #184, #185 and #143 cover and the issue puts out of scope. The pull request's CI
confirmed the miss; the owner chose those issues, and #221 measures again after them.

## Consequences
Every run, in tests and real tickets, starts fewer git processes per round, with the same
guarantees. A new part of the guard's snapshot should be read by one of the three processes of
`git.state` or from a file, not by a new process per verification. `tests/process_phases.py`
names the phase of each function; a renamed or new phase function is added there, or its calls
count as setup. The bounds of `test_c11_fewer_processes` record the counts: a change that adds
git processes to a run raises one of them deliberately, in its own ADR.

## Alternatives considered
- One listing of the remote for the whole replay instead of one per check (the issue's example):
  checks run one after another in their own trees, so a first check could push a tag and a later
  one delete it, and a single listing after the last check would see the remote as at the start.
  Listing after each check stops the ticket on the first change, before the next check runs.
- Parsing the git configuration files in Python instead of `git config --list --show-scope`:
  includes, conditional includes, the global and system files and quoting rules would be
  reimplemented, and the guard must see what git sees.
- Caching the git folders between verifications: an agent can point the tree's `.git` file
  elsewhere, and the snapshot must follow git's own resolution each time.
- Caching the ancestry per head and adding the shallow file and the replacement refs to the
  snapshot: the ancestry git computes also depends on the commit-graph files, the grafts file and
  configuration (`core.commitGraph`, `GIT_REPLACE_REF_BASE`), and missing one input would let a
  check change the history unseen; one `merge-base` per verification sees them all.
- Reading refs from `packed-refs` and `refs/` directly: it misses the reftable format and
  symbolic refs, which `for-each-ref` handles.
- Batching the record commits of a phase into one: each record commit is already the only one
  of its phase (the folder opened, the checks and the delivery, the pull request), and the last
  one must come after the push.
