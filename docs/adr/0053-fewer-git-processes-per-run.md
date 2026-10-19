# 0053. Fewer git processes per run: one read of git per verification, one remote listing per replay, three processes per record commit

- Status: accepted; the Windows figures are pending until the pull request's CI has run (see
  "Durations")
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

## Measurements before the change
`tests/process_phases.py` counts the processes Ariane starts through `process.run` during a
block, by phase. A call's phase is set by the innermost frame of Ariane's code that names one
(for example `flow._TicketRun.verify` for guard verification, `git.remote_refs` for remote
listing, `flow._TicketRun._commit_record` for record commits). A call that no such frame names
(preparing the tree, opening the ticket folder, reading the head) counts as setup. Counted on
Linux, on the code before this change (`HEAD` of `main` when #214 opened) and after, with the
same counter:

| Run | setup | session | guard verification | remote listing | replay | review | record commits | delivery | total |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Go on the first round, before | 11 | 7 | 46 | 5 | 3 | 6 | 12 | 3 | 93 |
| Go on the first round, after | 11 | 6 | 22 | 5 | 3 | 6 | 9 | 3 | 65 |
| Three no-go rounds to a draft, before | 13 | 29 | 108 | 11 | 9 | 18 | 12 | 3 | 203 |
| Three no-go rounds to a draft, after | 13 | 26 | 48 | 11 | 9 | 18 | 9 | 3 | 137 |
| Restart after a stop, before | 29 | 7 | 46 | 5 | 3 | 6 | 12 | 3 | 111 |
| Restart after a stop, after | 29 | 6 | 22 | 5 | 3 | 6 | 9 | 3 | 83 |
| Go with three checks, before | 11 | 7 | 68 | 7 | 9 | 6 | 12 | 3 | 123 |
| Go with three checks, after | 11 | 6 | 30 | 5 | 9 | 6 | 9 | 3 | 79 |

Before the change, guard verification was by far the costliest phase: about half of every run.
Each verification started ten git processes: `rev-parse` twice for the git folders,
`git config --file -` for the shared config's keys, `git config --list --show-origin
--show-scope`, `for-each-ref`, `rev-parse --verify` for the base's tracking ref, then
`symbolic-ref` for the branch, `merge-base --is-ancestor`, `rev-parse HEAD` and `ls-remote`. The
next costliest were the record commits (four processes each) and, with several checks, one remote
listing per check.

## Decision
Three cuts: guard verification, remote listing and record commits. The session phase also gains,
because it shares the commit.

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
  checks the branch, the ancestry, the expected head, git and the instruction files, in that
  order, with the same stops. A verification therefore runs three processes, plus
  `merge-base --is-ancestor` for a head not verified before, plus the remote listing.
- **The ancestry once per head.** `merge-base --is-ancestor start head` runs only for a head this
  run has not verified yet. A commit id fixes its whole history, so a head already verified to
  descend from the start commit still does. The head itself is compared every time.
- **The replay and reviewer trees in one process.** `git.detached_head` (`rev-parse HEAD
  --symbolic-full-name HEAD`) replaces `symbolic-ref` plus `rev-parse HEAD` for a tree that
  must stay detached at the checked commit (`replay`, `ariane verify`).
- **One remote listing for the replay.** Each check's verification no longer lists the remote
  (`verify(..., remote=False)`). `flow._TicketRun.verify_remote` lists it once, after the last
  check of the round and before any review, with the same comparison (`git.remote_changes`), the
  same stop ("the remote changed during the checks") and the same count of guard violations. The
  agent session, the reviewer and the delivery each still list it once.
- **Three processes per record commit.** `git.commit` runs `reset`, `add`, `commit`, and compares
  the index with HEAD (`git diff --cached --quiet`) only when `git commit` refused. If nothing is
  staged it still returns False; any other refusal raises `GitError`. The `reset` first also
  clears a merge state an agent may have left (`MERGE_HEAD`), as before, so a commit without a
  change is never a merge commit.

What each cut keeps:

- *Guard (ADR 0017):* the parts compared are the same, with the same keys and the same values for
  every part except `keys <path>`, whose value is the text it was parsed from (it changes exactly
  when that text changes). The same parts are tolerated for another run (`runs.foreign_changes`,
  unchanged in what it drops). The shared config's digest and keys still come from one read of
  the file. The reads still happen after the survivors are killed and before the registry is
  read. Every stop the guard raised before, it raises now, with the same reason. The tests below
  show this for a planted hook, a config key, a comment in the shared config, a local branch, a
  tag, the base's tracking ref, a detached HEAD, a rewritten history and a pushed remote branch.
  They also cover a check that pushes a tag to the remote, and a reviewer that commits on the
  ticket branch (the head checked even when its ancestry is known).
- *Clean-tree replay (C9, ADR 0041):* unchanged. Each check still gets its own fresh tree,
  created, set up, run, verified and removed; only the remote listing moved to after the last
  check. A check that changes the remote still stops the ticket before any review or push. A
  later check of the same round may run first, in its own tree, with nothing pushed.

Regression checks, `tests/test_c11_fewer_processes.py` (`uv run pytest -k c11_fewer_processes`):

- the four runs of the table stay within their "after" counts per phase. A later change that
  raises one fails, and raising a bound needs a new decision;
- `git.state` starts three processes, with a branch listed before the checked-out one (the
  `%(HEAD)` mark is read whatever the line), and a record commit starts `reset`, `add`,
  `commit`;
- the guard stops on each tampering listed above.

The tests that existed are unchanged, with one exception.
`test_c11_parallel_guard_another_run_writing_during_the_baseline_is_tolerated` used to write
just before the `git config --file -` call. That call no longer runs while the snapshot is taken,
so the test now writes just before the read of the folders, which is followed by the read of the
shared config. Its assertion is the same.

## Durations

| Where | Before (the code of `main` when #214 opened) | This change |
| --- | --- | --- |
| Linux sandbox, git processes of a go run / three no-go rounds / a restart | 93 / 203 / 111 | 65 / 137 / 83 |
| Linux sandbox, sum of the 30 slowest tests (`--durations=30`, back to back) | 118.5 s | 108.4 s |
| Linux sandbox, whole-run tests among them (for example a draft delivery record, three no-go rounds) | 3.68 s, 3.24 s | 2.58 s, 2.78 s |
| Windows CI, sum of the 30 slowest tests | ADR 0049's list: 30 tests from 48.7 s down to 22.4 s (run 39153818737) | pending |

The sandbox's sum of the 30 slowest includes tests that wait on purpose (process trees, idle
limits, parallel checks), which this change does not touch. In it, whole runs are 20 to 30 %
faster. Wall time in the sandbox varies from run to run (ADR 0049), so the CI figures are the
reference.

**The Windows target is not shown yet.** The implementer cannot run Windows. The pull request's
CI reports the 30 slowest Windows tests (`--durations=30`, ADR 0049). The owner records their sum
here, against the sum of ADR 0049's list, before merging; the target is at most 60 % of it. On
the counts alone, a whole run starts 30 to 33 % fewer processes, so the target may not be met by
this change alone. If the CI sum is above 60 %, the next cuts are, by the counts above: the review
phase (three diffs per round), the session phase (`ignored` twice and two diffs per session) and
the replay and reviewer trees themselves, which #184, #185 and #143 cover.

## Consequences
Every run, in tests and real tickets, starts fewer git processes per round, with the same
guarantees. A new part of the guard's snapshot should be read by one of the three processes of
`git.state` or from a file, not by a new process per verification. `tests/process_phases.py`
names the phase of each function; a renamed or new phase function is added there, or its calls
count as setup. The bounds of `test_c11_fewer_processes` record the counts: a change that adds
git processes to a run raises one of them deliberately, in its own ADR.

## Alternatives considered
- Parsing the git configuration files in Python instead of `git config --list --show-scope`:
  includes, conditional includes, the global and system files and quoting rules would be
  reimplemented, and the guard must see what git sees.
- Caching the git folders between verifications: an agent can point the tree's `.git` file
  elsewhere, and the snapshot must follow git's own resolution each time.
- Reading refs from `packed-refs` and `refs/` directly: it misses the reftable format and
  symbolic refs, which `for-each-ref` handles.
- Batching the record commits of a phase into one: each record commit is already the only one
  of its phase (the folder opened, the checks and the delivery, the pull request), and the last
  one must come after the push.
- Listing the remote once per round instead of once per phase: a reviewer or fix session would
  then run while the remote had changed during the checks.
