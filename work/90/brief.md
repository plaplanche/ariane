# Product brief: Run the opencode reviewer in the tree under review: pass --dir and PWD (C5, C10)

- Source: issue #90 (https://github.com/plaplanche/ariane/issues/90)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

Slice 3's gate run of #86 with `ARIANE_CONFIG=docs/ariane.opencode-reviewer.example.toml` (draft pull request #89) ended with three no-go reviews that all reported the change as missing, although the branch carries it (schema `if`/`then`, regenerated schema, `test_c5_opencode_schema_*`, documentation). opencode's own session store shows that the three reviewer sessions read `/home/user/ariane/...`, the repository's main checkout (code of `main`), and never `…/worktrees/86-replay`, the tree under review.

Cause, reproduced on a throw-away repository with a git worktree: opencode takes its working directory from the `PWD` environment variable, not from the process's working directory. Ariane starts opencode with `cwd` set to the replay tree, but the session's environment is a copy of Ariane's own, whose `PWD` is the directory Ariane was started from. With a stale `PWD`, opencode reads the other tree; with `--dir <tree>` it reads the right one even when `PWD` is stale. A reviewer that reads another tree than the one under review makes every opencode review meaningless. Spec: C5, C10.

## Current state

- `src/ariane/opencode.py:65`: `command` builds `opencode run --pure --format json --model … --agent …`, without `--dir`.
- `src/ariane/opencode.py:78`: `environment` returns `session.env` plus the `OPENCODE_*` variables; `PWD` is whatever Ariane's environment holds.
- `src/ariane/opencode.py:103`: the process is started with `cwd=session.cwd`.
- `docs/architecture/modules/opencode.md`: describes the command line and the environment, without `--dir` or `PWD`.

## Decided spec

- `command` passes `--dir <session.cwd>` (absolute path) to `opencode run`.
- `environment` sets `PWD` to the same absolute path, so nothing opencode starts sees a stale directory either.
- The Claude Code runtime and the checks are unchanged.

## Release note

Fixed: an opencode reviewer reads the working tree under review, not the directory Ariane was started from.

## Acceptance criteria

- A test named `test_c5_opencode_dir_*` shows that the command line holds `--dir` followed by the session's working tree, and that the environment's `PWD` is that tree even when the base environment holds another `PWD`.
- All checks in CLAUDE.md pass.

## Acceptance checklist

- [ ] `uv run pytest -k c5_opencode_dir` runs at least 1 test and it passes.
- [ ] All checks in CLAUDE.md pass.
- [ ] Definition of done, documentation (C25): `docs/architecture/modules/opencode.md` updated (command line with `--dir`, `PWD` in the environment).

## Out of scope

- Re-running the review of #86: done by hand after this ticket is merged (`ariane verify ariane/86 --issue 86` with the opencode configuration).
- Setting `PWD` for the Claude Code runtime or for the checks.

## Related

#86, #89, #83, ADR 0029, spec C5, C10, C25.
