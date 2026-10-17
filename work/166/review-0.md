# Review 0

- Reviewed commit: `66cdeffbbd85e393ab5dcbd098cb15a8194047a9`
- Reviewer model: claude-opus-5-5
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`tests/test_c11_guard_hardening.py:76`) The pushInsteadOf test is caught by the reviewer guard, not the new delivery guard

  `late` adds `url.….pushInsteadOf` during the reviewer session. The existing `after_session` guard in `replay.review_round` (`replay.py:132-133`, `run.verify("the reviewer", …)`) already sees the `.git/config` digest change and stops the run, so this test passes without `Delivery.guard`, `_guard_delivery` or `url_rewrites`. The acceptance criterion asks for a key added *after the last agent session*, between the last guard and `git.push`. Nothing tests that path, for example by adding the key from a patched `commit_record` or before `_require_replayed`. The companion test `..._delivery_runs_the_guard_right_before_the_push` only checks that `url_rewrites` is called before `push`. If `url_rewrites` always returned `[]`, or `_guard_delivery` ignored its result, every test would still pass. The stopping behaviour has no test.

- **blocking** (`tests/test_c11_guard_hardening.py:152`) The verify records symlink test never runs verify

  `test_c11_guard_hardening_verify_records_replace_a_symlinked_checks_file` calls `ticket.write_file` and `ticket.ensure_folder` directly on a folder it creates itself. It never runs `verify`, and never puts the symlink in the branch at `work/verify/<branch>/checks.md`. Reverting `_Verification._commit` (`verify.py:344-347`) to the old `mkdir` + `write_text` would leave this test green. The acceptance criterion (a symlinked `work/verify/<branch>/checks.md` is replaced, not followed) is not shown for verify, which is the code path the issue names.

- **minor** (`tests/test_c11_guard_hardening.py:69`) Tautological assertion in the driver test

  `assert (git.committed_paths(...) == [...][::-1] or True)` is always true. The test only exercises `git.diff`. Removing `NO_DRIVERS` from `committed_paths`, `changed_paths`, `Delivery._require_replayed` or verify's `diff --name-only` would not fail it. Note that `--name-only` diffs do not run drivers anyway, so only `git.diff` really matters, but the assertion should be removed or made real. The `#!/bin/sh` driver script may also behave differently on the Windows CI runner.

- **minor** (`src/ariane/verify.py:199`) A git command runs after untrusted setup and before the guard

  In `replay_each`, the order is: `setup` (untrusted command) → `git.untracked(replay)` (`ls-files --others`) → `run_check` → `_unchanged` (snapshot compare). The spec asks that the snapshot be compared before any other git command after untrusted code runs, but `ls-files` runs with a config the setup may have changed. The risk is low: `ls-files --others` runs no filters, and hooks and fsmonitor are neutralised by `_SAFE_OPTIONS`. Comparing the snapshot after setup, or moving the guard ahead of `untracked`, would close it. Also, after a refusal, the `finally: remove(tree)` still runs `git worktree remove`. The test allows this, but it is a literal deviation from "runs no further git command".

- **minor** (`src/ariane/git.py:260`) `url_rewrites` fails open

  `git config --local --name-only --list` uses `check=False`. If the command fails (for example on a malformed local config), the function returns `[]` and the rewrite check passes silently. The `verify` call that follows would most likely raise `GitError` on the same config, so this is defence-in-depth only. Failing closed (stop when the listing fails) would be safer. Worktree-scope (`config.worktree`) `insteadOf` keys are not listed either; the snapshot covers them only when they change.

- **minor** (`docs/architecture/modules/shadow.md:40`) shadow.md and replay.md not updated for the changed signatures

  `ShadowRun._deliver` now takes `unchanged` and `guard_push`, but `shadow.md:40` still shows `_deliver(checked, settled, reviewed, results)`. `replay.review_round` now takes the instructions from `run.base_instructions` instead of reading git, and `replay.md` does not say so. Ariane flagged both documents as mapped to changed files and left untouched.

- **minor** (`src/ariane/delivery.py:72`) The records commit runs before the last guard

  Writes in `deliver`, in order: journal "Delivering", `status.md` "pushed", records commit, `_require_replayed`, `guard()`, push. The `git commit` therefore runs with whatever config a lingering process may have planted after the last agent guard (for example `commit.gpgsign` + `gpg.program`). If the guard then stops the run, the committed `status.md` says "pushed". In flow, `metrics.finish("delivered")` is also called before `deliver()`. The issue only asks for the guard right before `git.push`, so this is not blocking. Running the guard once before `commit_record` as well would close the gap.

- **blocking** Definition of done not met: The change is covered by tests that fail without it.

  Four of the acceptance criteria have tests that fail without the change: verify refuses on a `.git/config` change, `git.diff` ignores drivers, the moved remote-tracking ref stops the run, and the instructions are read before any agent runs. Two do not. The pushInsteadOf test passes without the delivery guard because the reviewer's post-session guard catches the key. The symlink test calls `ticket.write_file` directly and never goes through `verify._commit`.

- **blocking** Definition of done not met: The documentation the change affects is updated (C25).

  These are updated: `git.md`, `verify.md`, `delivery.md`, `flow.md` and `ticket.md`. No log line was added, so `docs/logs.md` is unaffected. Not updated: `docs/architecture/modules/shadow.md` (stale `_deliver` signature) and `replay.md` (`review_round` now uses `run.base_instructions`), both flagged by Ariane. These gaps are minor; the four documents the issue names are done.

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

- **not met**: The change is covered by tests that fail without it.

  Four of the acceptance criteria have tests that fail without the change: verify refuses on a `.git/config` change, `git.diff` ignores drivers, the moved remote-tracking ref stops the run, and the instructions are read before any agent runs. Two do not. The pushInsteadOf test passes without the delivery guard because the reviewer's post-session guard catches the key. The symlink test calls `ticket.write_file` directly and never goes through `verify._commit`.

- **not met**: The documentation the change affects is updated (C25).

  These are updated: `git.md`, `verify.md`, `delivery.md`, `flow.md` and `ticket.md`. No log line was added, so `docs/logs.md` is unaffected. Not updated: `docs/architecture/modules/shadow.md` (stale `_deliver` signature) and `replay.md` (`review_round` now uses `run.base_instructions`), both flagged by Ariane. These gaps are minor; the four documents the issue names are done.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  The ADR 0017 amendment records the open choices: the private ref `refs/ariane/base-check` for the fast-forward fetch, the extra delivery guard, and `NO_DRIVERS`. The ADR 0028 amendment supersedes the old no-snapshot decision and records `ensure_folder`/`write_file`.

## Proposed learnings (not decided)

- A test for a guard that only runs "after the last session" must make its change after that session, for example from a patched commit or push step. A change made inside a session is caught by the per-session guard that already exists.
- Acceptance tests for a code path, like verify's records, must go through that path, not call the helper it was refactored to use.
- Replace `assert X or True` with a real assertion or remove it; lint does not catch it.
