# Product brief: Commit only the intended paths, never the whole index (C9, C11)

- Source: issue #54 (https://github.com/plaplanche/ariane/issues/54)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

The second independent review of slice 2 found that Ariane's commits take whatever is already staged in the index, not only the paths Ariane means to commit. A check written by the agent can run `git -C <ticket worktree> add evil.py` during the replay: the guard after the checks passes (the index is not in its snapshot), and the commit "record the checks and the delivery" carries `evil.py`, which is pushed with green `ariane/*` statuses although it was never replayed. Likewise an agent that only stages a change to another ticket's records (`git add work/3/journal.md`) gets it into Ariane's commit of its work, past the record guard that only looks at commits. Reproduced on a scratch repository: a file staged before `git add --all -- work && git commit -m ...` ends up in the commit. Spec: C9 (statuses from the replayed commit), C1 (other tickets' records untouched), C11; ADR 0018 (the delivered commit is the replayed one).

## Current state

- `src/ariane/git.py` `commit()` runs `git add --all -- <pathspec>`, then `git commit --quiet -m <message>` with no pathspec: the whole index is committed.
- Callers: `src/ariane/flow.py` `_commit_agent_work` (pathspec `.` and `:(exclude)work`) and `_commit_record` (pathspec `work/<n>`).
- The guard after a session or the checks compares branch, HEAD, git configuration, hooks, local refs and the remote, not the index.
- `src/ariane/cli.py` `_status`: when `work/<n>/` is on the remote base branch but its `status.md` is not, `git.show_on_branch` raises `GitError` and the user gets a traceback (C23 promises one line).
- `tests/test_flow_setup_env.py` (#48): the test token is passed in the `environ` argument, not in `os.environ`, so the token assertions and the negative control pass even with the full process environment; only the push and record-count assertions really detect a regression.

## Decided spec

- `git.commit` resets the index to HEAD (`git reset --quiet`) before staging its pathspec, so a commit holds only that pathspec's changes.
- Before the push, Ariane checks that `git diff --name-only <replayed commit> HEAD` lists only paths under `work/<n>/`; otherwise the ticket stops before any push, naming the paths.
- `ariane status <n>` answers in one line when the remote base branch has `work/<n>/` without a readable `status.md` (merged, last action unknown).
- `tests/test_flow_setup_env.py` puts the tracker token in the process environment (`monkeypatch.setenv`) so its token assertions and negative control fail when the setup gets the full environment.

## Release note

Security: Ariane commits only the paths it means to commit; a file staged by the agent or by a check no longer rides along.

## Acceptance criteria

- Tests named `test_c11_index_*` show that: a file staged by a check during the replay is not in the delivered commit; a change to another ticket's records that the agent only staged is not committed; the pre-push check stops a ticket whose head differs from the replayed commit outside `work/<n>/`.
- A test named `test_c23_status_merged_without_status_file_*` shows the one-line answer.
- The setup-environment tests fail if `_setup` is given the full environment (negative control run).
- All checks in CLAUDE.md pass.

## Acceptance checklist

- [ ] `uv run pytest -k "c11_index or c23_status_merged_without_status_file"` runs at least 4 tests and they pass.
- [ ] `uv run pytest -k c9_setup_without_credentials` passes with the token in the process environment.
- [ ] All checks in CLAUDE.md pass.

## Out of scope

Reading `HOME` files such as `~/.netrc` (sandbox, slice 9); the fast-forward fetch by remote name (fails closed).
