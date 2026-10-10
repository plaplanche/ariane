# Review 1

- Reviewed commit: `3e91a2f3d507b2859a175feff3b05e4e63ebdf03`
- Reviewer model: claude-opus-5-5
- Verdict: **go**

## Findings

- **minor** (`tests/test_c5_opencode.py:277`) The reviewer-env test checks ANTHROPIC_API_KEY but not CLAUDE_*

  The acceptance criterion says the reviewer's environment does not hold `ANTHROPIC_*`/`CLAUDE_*`. The test only puts `ANTHROPIC_API_KEY` in the environment and checks that it is absent. A `CLAUDE_` variable is never seeded or asserted. The behaviour is correct, because `context.untrusted_environment` keeps only the role runtime's prefixes, but the coverage is half of what the criterion names.

- **minor** (`src/ariane/verify.py:276`) The 'nothing was recorded' reason is generic

  When `git add` refuses an ignored `work/`, the reason given is 'git found nothing to commit under work/verify/<branch>', which hides that the path is ignored. The next action ('check that work/ is not ignored') makes up for it. Returning or raising the ignore message from `git.commit` would make the `<reason>` the spec asks for more accurate.

- **minor** (`src/ariane/verify.py:258`) Records stay in the user's checked-out tree when the commit is refused

  When the branch is checked out (`self.where`), `review.md`/`checks.md` are written there before `git.commit`. If nothing is committed, the files stay in the user's tree. They are ignored in the case that triggers this, so the harm is small, but they are not cleaned up.

- **minor** (`src/ariane/verify.py:228`) A short race window remains between `_before_commit` and the commit

  The re-check runs just before `_commit`. A temporary worktree add or a write can still happen between the two. This is acceptable and much narrower than before (minutes down to milliseconds); the note is for completeness.

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

  These tests fail on the base: `test_c5_opencode_stdin_*` (3: no message argument, `input_text`, a 300,000-character prompt through `fake_opencode.py` with `stdin_size`). `test_c21_role_env_*` (2: implementer and fix sessions lack `OPENAI_API_KEY`, which the union used to give them). `test_c23_verify_records_*` (5): the ignored `work/` case checks for 'nothing was recorded', which the base never printed (it raised a GitError instead); the checked-out-elsewhere and dirtied-tree cases committed or failed differently before; the moved-branch case uses a monkeypatched `_unchanged` so that only `_before_commit` can catch it. `test_c5_opencode_cli_runtime_*` (1). `test_git.py` covers `tolerate_ignored`. That makes 11 tests, at least the 7 the checklist requires.

- met: The documentation the change affects is updated (C25).

  ADR 0029 is amended (standard input, environment per role, alternatives and consequences). `modules/opencode.md`, `runtime.md`, `flow.md`, `review_session.md`, `verify.md` and `process.md` are updated (`opencode` caller and `_shown` 200-character cut). `git.md` describes the new `commit` behaviour. The 'docs: references' check passes, and no log event was added.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  The issue decided the behaviour (stdin, environment per role, verify refusals), and ADR 0029 is amended to match. `tolerate_ignored` and the LC_ALL=C detection are implementation details recorded in `git.md`, not open spec choices.

## Proposed learnings (not decided)

- When a test is meant to show that a later guard catches a race, disable the earlier guard that would also catch it (as done with `_unchanged`). Otherwise the test passes on the base too.
- Matching git's English messages needs LC_ALL=C. Under C, gettext also ignores LANGUAGE, so the match is stable across locales.
- Acceptance criteria that name a whole family of variables (ANTHROPIC_*/CLAUDE_*) should be tested with one variable of each prefix.
