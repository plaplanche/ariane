# Review 0

- Reviewed commit: `51d31c46e25c624fb8b2521fa159b58868eab43c`
- Reviewer model: claude-opus-5-5
- Verdict: **go**

## Findings

- **minor** (`docs/architecture/modules/git.md:24`) Callee modules' collaboration diagrams do not list the new `verify` caller

  The module docs list both callees and callers (for example `flow --> git`, `delivery --> checks`). `verify` now calls git, checks, review_session, review, flow, ticket, context, process, redact, config, runtime and tracker, but none of those module files has a `verify --> <module>` arrow. This includes git.md, which this change edits. The level 3 view and verify.md are correct, so this is only a gap in the per-module diagrams, not a wrong statement.

- **minor** (`src/ariane/verify.py:242`) `git.commit`'s return value is ignored, but the output always says "Records committed"

  `git.commit` returns False and commits nothing when the pathspec stages no change, for example in a project whose .gitignore covers `work/`. `_replay_and_review` still prints "Records committed on the branch" and can exit 0. It should check the result and refuse, or say that nothing was recorded.

- **minor** (`src/ariane/verify.py:222`) Race between the start-time checks and the commit

  `_checkout` checks once, at the start, where the branch is checked out and whether that tree is dirty. The commit happens minutes later. If the user checks out the branch in another tree in the meantime, `worktree add` fails after the review is done and the records are lost. If the user commits on the branch, `_unchanged` catches it only at the review callbacks. Also, `git.commit` runs `git reset` on the user's index, which unstages anything they staged in the meantime. Re-checking `worktree_of` and cleanliness just before committing would close the gap.

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

  tests/test_verify.py adds 8 `test_c23_verify_*` tests. They cover: green plus `go` gives the records committed and exit 0; a failing check gives exit 1 with the next action; `no-go` gives exit 1; a dirty checked-out branch is refused, naming `M app.txt`; a clean checked-out branch gets the commit in its tree; the issue text vs the commit messages reach the reviewer; an unknown branch is refused; no working tree is left behind. Pushes are tracked through a monkeypatched `git.push` plus a comparison of the remote branches. All of them import `ariane.verify`, which does not exist without the change.

- met: The documentation the change affects is updated (C25).

  Updated: docs/reference/cli.md regenerated with `verify`; the new modules/verify.md; cli.md, git.md and logs.md; 3-components.md (component edges, the review_session edges asked for by the #34 follow-up, a new verify sequence); the first line of delivery.md; the README usage; CLAUDE.md's hand-takeover line. Remaining gap (minor): the callee modules' diagrams do not show `verify` as a caller.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  docs/adr/0028-verify-implementation.md records the open choices: where the replay tree lives, the reviewer context and the merge base, running the review even when a check fails, where the commit is made, behaviour when setup or the reviewer fails, and skipping the git-config snapshot.

## Proposed learnings (not decided)

- Module docs list callers as well as callees: when a new module calls existing ones, add `new --> module` arrows to each callee's modules/<module>.md, not only to the new module's file and the level 3 view.
- When a helper returns whether it acted (like `git.commit` returning False), the user-facing line should depend on that result.
