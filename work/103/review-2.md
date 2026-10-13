# Review 2

- Reviewed commit: `3c21191b53cab6ca79d4634881f0109656e6bc50`
- Reviewer model: claude-opus-5-5
- Verdict: **go**

## Findings

- **minor** (`docs/adr/0031-reviewer-isolation.md:46`) Residual vector understated: CLAUDE.md in the ancestors of the reviewer tree

  The ADR only names CLAUDE.md files in the ancestors of the empty temporary working directory. The reviewer tree `<repo>.ariane/worktrees/<n>-review` sits next to the implementer's working tree, so an implementer running without a sandbox can also write `<repo>.ariane/worktrees/CLAUDE.md` or `<repo>.ariane/CLAUDE.md`. Claude Code may load these when it reads files under the --add-dir tree. Both cases belong to the same class (no OS sandbox, slice 9), but the ADR should name them, or Ariane should check before the session that no instruction file exists in those ancestors.

- **minor** (`src/ariane/verify.py:192`) Removing the reviewer tree in verify is not failure-tolerant

  `git.remove_worktree` in the `finally` block raises if removal fails (for example a locked file on Windows). That error can hide the review outcome, or an earlier exception. flow.py uses `_remove_replay`, which logs a warning instead. Consider the same tolerance here.

- **minor** (`tests/test_c10_reviewer_isolation.py:84`) Weak assertion for the '(none)' case

  `section.lstrip().startswith("(none)") or "(none)" in section.split("Diff from")[0]` would also pass if another '(none)' (for example the sentences list) came after the heading. Asserting `section.lstrip().startswith("(none)")` alone is stricter.

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

  tests/test_c10_reviewer_isolation.py adds 11 tests (one of them parametrized four ways) named test_c10_reviewer_isolation_*. They cover: the reviewer tree has no CLAUDE.md, AGENTS.md or .claude at any depth while the replay tree keeps them; case-insensitive removal; symlinks that leave the tree; reviewer argv has --restricted and --add-dir, with no bypassPermissions and no setting sources; implementer argv unchanged; empty cwd; WebFetch, Task, Bash and Write refused at load; the prompt holds the base CLAUDE.md and not the branch's; verify uses a -reviewer tree; opencode runs in the clean tree. test_docs_reference adds a schema test. Each depends on code this change adds (add_dirs, add_reviewer_worktree, REVIEWER_TOOLS, the prompt section), so it would fail without the change.

- met: The documentation the change affects is updated (C25).

  New ADR 0031; ADR 0029 has an amendment pointing to it; see-also notes in ADRs 0010, 0016 and 0025. Module docs updated: claude_code.md, review_session.md, review.md, config.md, config_schema.md, git.md, runtime.md, flow.md, verify.md. C4 files 2-containers.md and 3-components.md updated. docs/reference/ariane.toml.schema.json regenerated (the docs: references check passes). README has a paragraph on the reviewer's tools.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0031 records the choices left open: the -reviewer tree name in verify, removing symlinks that leave the tree, removing a tree that cannot be built, Session.add_dirs as the carrier, '(none)' when the file is absent, and the residual vector through the temporary directory.

## Proposed learnings (not decided)

- When moving a session to an empty cwd plus --add-dir, check every ancestor directory that Claude Code may scan for CLAUDE.md (of the cwd and of each added dir), and record the ones a sandbox-less implementer can write.
- Cleanup of temporary worktrees in finally blocks should log a warning rather than raise, so a cleanup failure does not hide the real outcome.
