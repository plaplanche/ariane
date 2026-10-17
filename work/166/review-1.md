# Review 1

- Reviewed commit: `6251f3730352a336d6a7676a159100c65ff02318`
- Reviewer model: claude-opus-5-5
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/shadow.py:105`) Shadow mode reviewer silently loses the base branch's instructions

  `replay.review_round` now passes `run.base_instructions` (src/ariane/replay.py:144) where it used to call `git.base_instructions(run.worktree, run.remote, ...)`. Only `flow.start` sets that value: `_TicketRun.__init__` defaults it to "" (flow.py:134), and `ShadowRun.__init__` calls `super().__init__(..., clone, branch_name(...), "")` without passing it. `shadow._prepare` (shadow.py:67-88) never reads the instructions either. Before this change the shadow reviewer got the `CLAUDE.md` at `refs/remotes/shadow/<base>` in the clone. Now every shadow review runs with empty base instructions. That is a behaviour regression in the mode the spec uses to compare Ariane with the current process, and no test catches it. Fix: read `git.base_instructions(clone, BASE_REF_REMOTE, base)` in `shadow._prepare`, after the `update-ref` and before any agent runs, pass it to `ShadowRun`, and add a shadow test that asserts the reviewer prompt contains the base rule.

- **minor** (`src/ariane/flow.py:325`) `_snapshot` hard-codes REMOTE, so shadow mode guards a ref that does not exist

  `_TicketRun._snapshot` uses `refs/remotes/{REMOTE}/...` (origin) instead of `self.remote`. In a shadow clone the base ref is `refs/remotes/shadow/<base>` and `origin` has been removed. The new snapshot part is therefore always "", and a session that moves the shadow base ref is not caught. Use `self.remote`.

- **minor** (`tests/test_c11_guard_hardening.py:50`) The verify refusal test does not show that no further git command runs

  The acceptance criterion says verify 'runs no further git command' after the refusal. The test only checks that no `status`, `commit` or `ls-remote` runs after the last `config` call. In fact `replay_each`'s `finally: remove(tree)` still runs `git worktree remove --force` after `_git_unchanged` raises. It runs with the safe options, so the risk is small. Either the test or the criterion should state this exception honestly. Also, a failing setup raises `Refused` before `_git_unchanged("the setup")` (verify.py:194-199), so a setup that edits `.git/config` and then exits non-zero is reported as a setup failure, not as a git change.

- **minor** (`src/ariane/git.py:260`) `url_rewrites` does not follow includes and ignores worktree scope

  `git config --local --name-only --list` does not expand `include.path` or `includeIf`, and it does not read `config.worktree`. A `pushInsteadOf` placed in an included file is not listed. The snapshot catches changes made during the run, so this only matters for configuration that already existed. Consider adding `--includes` or reading every scope.

- **minor** (`src/ariane/flow.py:325`) Out of scope (#159): guarding `refs/remotes/origin/<base>` stops a run when the owner or a parallel run fetches the base

  Any `git fetch` of the base branch in the main checkout during a ticket, whether by the owner or by another ticket's `_prepare`, now changes the snapshot and stops the run (and the same in verify). The ticket asks for this, but parallel-run tolerance belongs to #159, which should account for it.

## Definition of done

- met: check lint passes

  Replayed by Ariane: exit 0.

- met: check format passes

  Replayed by Ariane: exit 0.

- met: check types passes

  Replayed by Ariane: exit 0.

- met: check tests passes

  Replayed by Ariane: exit 0.

- met: check file length passes

  Replayed by Ariane: exit 0.

- met: The change is covered by tests that fail without it.

  tests/test_c11_guard_hardening.py has 7 `test_c11_guard_hardening_*` tests. Each one would fail without the change: the verify config edit, the ext-diff/textconv driver, the pushInsteadOf before the push, guard-then-push order, the moved tracking ref, base instructions, and the symlinked checks.md. The shadow-mode regression is not covered (see the blocking finding).

- met: The documentation the change affects is updated (C25).

  docs/architecture/modules/git.md, verify.md, delivery.md and flow.md are updated, as are replay.md, shadow.md and ticket.md. No log event was added (guard.verified is reused), so docs/logs.md is unchanged.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0017 amendment: safer reads, the private ref `refs/ariane/base-check` for the fast-forward check, and the last guard. ADR 0028 amendment: the verify snapshot, instructions read before the first check, and symlink-safe records.

## Proposed learnings (not decided)

- When a value that used to be computed at use time (here `git.base_instructions` in `review_round`) becomes a constructor argument with a default, check every subclass and constructor call (`ShadowRun`). A default of "" silently turns a feature off.
- Guard helpers on the base class should use the instance's own remote name (`self.remote`), not the module constant, so that subclasses such as shadow stay guarded.
- A test for 'runs no further git command' should assert on the full list of git calls after the refusal, including cleanup in `finally` blocks.
