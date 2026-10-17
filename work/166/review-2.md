# Review 2

- Reviewed commit: `0723bb487b5a7c9895278de570db32cd4228a4a7`
- Reviewer model: claude-opus-5-5
- Verdict: **go**

## Findings

- **minor** (`src/ariane/git.py:373`) One diff Ariane runs still lacks NO_DRIVERS

  The decided spec says to add `--no-ext-diff --no-textconv` to every diff Ariane runs. `git.commit` still runs `git diff --cached --quiet` without them. With `--quiet`, git only checks whether anything changed and produces no output, so drivers should not run in practice. For consistency with the rule (and the docs line 'every diff has NO_DRIVERS'), it should still get `*NO_DRIVERS`.

- **minor** (`src/ariane/verify.py:213`) After a verify refusal, `git worktree remove` still runs under the changed config

  Order on a check that edits .git/config: (1) the check runs; (2) `_unchanged` calls `_git_unchanged`, which takes a snapshot (`rev-parse`, `config --list`, `for-each-ref`, `rev-parse base_ref`) and raises Refused; (3) the `finally` in replay_each runs `git worktree remove --force` in repo_root, under the tampered configuration. That command still has `_SAFE_OPTIONS` (hooks off, fsmonitor off, ext transport off), and the test says so explicitly. It is a small residual, not a bypass, but neither ADR 0028 nor verify.md mentions it.

- **minor** (`src/ariane/git.py:452`) fast_forwarded leaves a private ref `refs/ariane/base-check` in the user's repository

  `verify` runs in the owner's repo_root, and `flow` runs in the shared common dir. When the remote base moves, the fast-forward check now creates `refs/ariane/base-check` and never deletes it. It is outside `refs/heads` and `refs/tags`, so the snapshot does not see it, and it does no harm. Still, it is a leftover the docs do not mention as persistent, and it keeps objects reachable.

- **minor** (`tests/test_c11_guard_hardening.py:59`) The driver test relies on a POSIX shell script and chmod

  CI runs on Windows, macOS and Linux. The test writes a `#!/bin/sh` script and uses `chmod 0o755` as `diff.external` and as the textconv driver. On Windows this depends on Git for Windows' bundled sh. The 'marker not created' assertion could then pass vacuously if the driver can never run there. A small Python driver invoked through `sys.executable` would make the test meaningful on every OS.

- **minor** (`tests/test_c11_guard_hardening.py:146`) The 'instructions read before any agent runs' test does not fail without the change

  `test_c11_guard_hardening_instructions_are_read_before_any_agent_runs` passes on the base commit too, because nothing moves the tracking ref. The real coverage comes from `reviewer_gets_the_instructions_of_the_fetched_base`, which fails without the snapshot's base_ref. No test checks the in-memory reading in a run where the ref moves without stopping, for example a legitimate remote fast-forward in a fix round. The criterion is still covered, but only through the stop.

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

  tests/test_c11_guard_hardening.py has 7 tests named test_c11_guard_hardening_*. The ones for verify refusing on a .git/config change, driver-free diffs, pushInsteadOf stopping the delivery, guard-before-push order, the moved tracking ref stopping the run, and the symlinked checks.md each fail on the base: before the change there was no snapshot in verify, no NO_DRIVERS, no url_rewrites or second guard, no base_ref in the snapshot, and write_text followed the link. Only the 'read before any agent runs' test would also pass on the base (minor finding).

- met: The documentation the change affects is updated (C25).

  docs/architecture/modules/git.md (NO_DRIVERS, url_rewrites, config_snapshot base_ref, fast_forwarded private ref), verify.md, delivery.md and flow.md are updated, as the checklist asks. replay.md, shadow.md and ticket.md are also updated for the signature and behaviour changes. No log-line key changed (guard.verified is reused), so docs/logs.md needs no regeneration. The docs: references check passes.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  The open choices are recorded as amendments: the private ref refs/ariane/base-check, so Ariane's own fetch does not trip the base_ref guard; a guard both before the records commit and right before the push; url_rewrites using --local --includes; and the records written through ensure_folder/write_file. They are in the 2026-10-17 amendments of docs/adr/0017-push-guard-revision.md and docs/adr/0028-verify-implementation.md, and the superseded 0028 decision is struck through.

## Proposed learnings (not decided)

- When a guard adds a remote-tracking ref to the snapshot, check every place where Ariane itself fetches into that ref; here fast_forwarded had to be redirected to a private ref, or the guard would trip on Ariane's own fetch.
- For 'X is read before any agent runs' criteria, a test needs the source to change mid-run without stopping; otherwise reading late and reading early look the same.
- Tests that use shell scripts as git drivers can pass vacuously on Windows CI; prefer a driver run through sys.executable.
