# Review 0

- Reviewed commit: `f77df5db169da6099fda4a3e33717c7bf194fdc6`
- Reviewer model: claude-opus-5-5
- Verdict: **go**

## Findings

- **minor** (`src/ariane/verify.py:199`) verify: setup output is read with git before the guard compares

  The issue says the snapshot is compared in `_unchanged` before any other git command. In `_setup`, the untrusted setup command runs and then `git.untracked(replay)` runs before `_unchanged` takes a new snapshot. On a failed setup, `Refused` is raised without comparing the snapshot at all. In both cases `replay_each`'s `finally: remove(tree)` then runs `git worktree remove`. Order of writes on this path: setup (untrusted) → `git ls-files` (untracked) → [Refused] → `git worktree remove`. `start` (`run.setup`) has the same order, and these commands run without credentials, so the risk is low. Comparing the snapshot right after the setup, and before `git.untracked`, would match the spec literally.

- **minor** (`tests/test_c11_guard_hardening.py:53`) 'runs no further git command' only patches git.diff

  The test fails only if `git.diff` runs after the guard trips. A regression that moves `changed_between`, `add_reviewer_worktree`, `status` or `remote_changes` ahead of the comparison would still pass. Patching `git.git` or `git.out` after the trip, with an allow-list for the worktree removal, would cover the criterion fully.

- **minor** (`tests/test_c11_guard_hardening.py:141`) The in-memory base instructions are not tested on their own

  In the `start` test the ref is moved inside the first reviewer session, after its prompt is built. The 'be kind' assertion would pass even if the instructions were still read at review time. The test only fails without the change because the watched ref trips the guard. Moving the ref during the implementer session, with the guard trip on the ref blinded, would show that the reviewer prompt uses the instructions read at preparation. The `verify` test likewise only checks the refusal.

- **minor** (`docs/architecture/modules/replay.md:12`) replay.md and shadow.md not updated for base_instructions

  `review_round` now takes the base instructions from `run.base_instructions` (read at preparation), not from git. `ShadowRun` now reads them in its constructor, and its `_deliver` gained `last_guard`. Neither `replay.md` nor `shadow.md` says so. Ariane flagged both files as mapped to the changed code but not touched.

- **minor** (`src/ariane/delivery.py:75`) The last guard runs after the records commit says 'pushed'

  Order of writes: `set_status('pushed', ...)` → `commit_record` (a git commit) → `_require_replayed` → `head` → `_last_guard` (`snapshot`/`remote_changes`, then a journal line) → `push`. If the last guard refuses, the branch keeps a committed status of 'pushed' until `_stopped` rewrites it. Nothing is pushed, so this is not a guard bypass, and no untrusted code runs between the reviewer's guard and this commit. Still, running the guard before the records commit, or rewording the status, would keep the records honest.

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

  `tests/test_c11_guard_hardening.py` has 8 test cases named `test_c11_guard_hardening_*` (one parametrized over `core.symlinks` true and false). Without the change, each would fail: `verify` has no snapshot, so the `.git/config` edit and the moved tracking ref go unnoticed and the reviewer runs; the diff test's driver marker would be written; `push_rewrites` and the `delivery` guard would not exist; without `unstage`, the `core.symlinks=false` case commits mode 120000 (the Windows failure). Some tests are weaker than the criteria (see the minor findings).

- met: The documentation the change affects is updated (C25).

  The checklist's files are updated: `git.md` (new functions, signatures, safe options), `verify.md`, `delivery.md` and `flow.md`; `ticket.md` too. No log line changed, so `docs/logs.md` needs no regeneration. The 'docs: references' check passes. `replay.md` and `shadow.md` miss small details (minor finding).

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  The ADR 0017 amendment records the choice to fetch from the URL in the fast-forward check, so that the guarded tracking ref does not move, together with the safer reads and the last guard. The ADR 0028 amendment records the snapshot in `verify`, reading the base instructions once, and the unstage-before-add rule for records.

## Proposed learnings (not decided)

- When a guard must run 'before any other git command', test it by failing on every git call after the untrusted step (patch `git.git`), not on one function.
- To show a value is captured early and kept in memory, change its source before the consumer reads it, not after.
- Tracking refs that the guard watches must not be updated by Ariane's own fetches; fetch from the URL into FETCH_HEAD instead.
- On Windows (`core.symlinks=false`), a committed link checks out as a plain file; drop the path from the index before `git add`, or the mode stays 120000.
