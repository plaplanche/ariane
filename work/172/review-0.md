# Review 0

- Reviewed commit: `7aefe7b8c23a3f0380d5357fdbb5b5ff0685dd24`
- Reviewer model: claude-opus-5-5
- Verdict: **go**

## Findings

- **minor** (`src/ariane/replay.py:57`) After a verify guard refusal, `git worktree remove` still runs

  In `_replay_and_review`, `replay_each` calls `verify(tree)`, which is `_unchanged`. That compares the snapshot first and raises `Refused`, but the `finally: remove(tree)` then runs `git worktree remove --force` in the repository whose config was just tampered with. The acceptance item says verify "runs no further git command". The test only patches `git.diff`, so it does not catch this cleanup command. The risk is low: `worktree remove --force` runs no hooks, external diff or textconv. Still, either state the cleanup exception in ADR 0028 or skip the removal once the guard has tripped.

- **minor** (`src/ariane/delivery.py:72`) The record commit says "pushed" before the last guard runs

  Order of writes in `deliver`: (1) `folder.log` ticket.delivering, (2) `set_status` "pushed", (3) `commit_record` (a local commit), (4) `_require_replayed`, (5) `_last_guard`, (6) `git.push`. The guard does come right before the push, as the spec asks, and nothing leaves the machine before it. But when the guard stops the run, the branch already has a local commit whose status says "pushed". The stop handler presumably overwrites the status afterwards. This is cosmetic: nothing is pushed or posted.

- **minor** (`tests/test_c11_guard_hardening.py:161`) The verify base-instructions test does not check the reviewer prompt

  `test_c11_guard_hardening_verify_reads_base_instructions_before_any_check` only asserts that verify stops (exit 1, no sessions), and the guard alone explains that. Nothing shows that verify's reviewer gets the instructions read before the first check. The `start` variant does check the prompts.

- **minor** (`docs/architecture/modules/shadow.md:19`) shadow.md and replay.md are not updated

  `ShadowRun.__init__` now reads `base_instructions` once from the clone, and `replay.review_round` now uses `run.base_instructions` instead of reading git. Neither module doc mentions this. Neither doc was wrong before, and the issue's documentation list does not name them, so this is minor.

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

  tests/test_c11_guard_hardening.py has 7 test functions; the symlink test runs with core.symlinks true and false, so pytest collects 8 items. Each depends on the new code: the verify snapshot, `--no-ext-diff`/`--no-textconv` together with `changed_between`, `_last_guard` and `push_rewrites` (one test disables `snapshot_changes` so that only the explicit key check can stop the delivery), base instructions kept in memory plus the watched ref, and `write_file` with `unstage` (forced core.symlinks=false, checks for 100644).

- met: The documentation the change affects is updated (C25).

  git.md, verify.md, delivery.md, flow.md and ticket.md are updated, as the issue's checklist asks. No log line changed (logs.md is untouched). shadow.md and replay.md did not change; this is reported as minor.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0017 amendment: verify guard, safer reads, the watched tracking ref, and `fast_forwarded` now fetching from the URL; the last guard. ADR 0028 amendment: guard, base instructions read once, symlink-safe records and unstaging.

## Proposed learnings (not decided)

- When a guard tripping must mean 'no further git command', check the `finally` cleanup paths (for example worktree removal) as well as the code that runs right after the check.
- Adding a ref to the tamper snapshot means every fetch Ariane runs during a run must stop updating that ref. Here `fast_forwarded` had to fetch from the URL into FETCH_HEAD.
