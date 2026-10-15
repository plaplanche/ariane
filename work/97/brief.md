# Product brief: Shadow mode: ariane start --shadow in a separate clone, agent push and PR attempts counted (C19, C23, slice 4)

- Source: issue #97 (https://github.com/plaplanche/ariane/issues/97)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

ADR 0030 items 3, 4 and 6: shadow mode lets a second user measure Ariane on real tickets while their current process does the real work, with no push, no pull request and no write to their repository (spec "Adopting Ariane on an existing project", step 2). Needs the metrics ticket of slice 4 merged first. Spec: C19, C23.

## Current state

- `src/ariane/flow.py:49` `worktree_path`, `:57` `start`, `:83` `_prepare`: a ticket runs in a git worktree of the user's repository on branch `ariane/<n>`, then `_check_and_deliver` (line 399) pushes, opens the pull request and publishes statuses.
- `src/ariane/git.py:197` `blocked_push_env` makes an agent's push fail without any record; `src/ariane/claude_code.py:214` and `opencode.py` read the session's event stream (tool calls with their command).
- `flow.py` is 585 lines (limit 600).

## Decided spec

- `ariane start --shadow <issue>` runs the same flow (setup, implementer, replay, review, fix rounds) in a separate local clone `<repo>.ariane/shadow/<n>/` made with `git clone --local` from the user's repository at the remote base branch, with the `origin` remote removed. Nothing is written to the user's repository: its `.git` is only read.
- It reads the issue from the tracker and nothing else: no push, no pull request, no commit status, no comment. It ends with one line: "Shadow ticket #<n> done (<outcome>, review <verdict>). Next: read <clone>/work/<n>/, then run ariane judge <n> accept|reject --minutes N."
- A clone that already exists stops the run with "remove it to start over", like a worktree today.
- Each runtime adapter reports, on `SessionResult`, the commands an agent attempted that push or open a pull request: a shell command whose words include `git push` or `gh pr create` (not `git pushd`, not a quoted string in `echo`). `metrics.json` gains `"attempts": {"push": n, "pull_request": n, "guard_violations": n}` per ticket, guard violations being the ones the existing post-session check detects. This applies to normal tickets too.
- `metrics.json` has `mode` `shadow`. Shadow handling lives in its own module; `flow.py` stays under 600 lines.

## Release note

New: `ariane start --shadow <issue>` runs a ticket in a separate clone without pushing or opening a pull request; agent push and pull-request attempts are counted.

## Acceptance criteria

- Tests named `test_c19_shadow_*` show, with the fake tracker and fake runtime: no push, pull request, status or comment call; the user's `.git` is byte-identical before and after (refs, config, worktree list); the clone has no `origin`; the final line; an existing clone stops the run.
- Tests named `test_c19_attempts_*` show: `git push origin x` and `gh pr create` counted; `git pushd`, `echo "git push"` not counted; the counts reach `metrics.json`; a guard violation is counted.
- All checks in CLAUDE.md pass.

## Acceptance checklist

- [ ] `uv run pytest -k "c19_shadow or c19_attempts"` runs at least 7 tests and they pass.
- [ ] All checks in CLAUDE.md pass.
- [ ] Definition of done, documentation (C25): new module doc in `docs/architecture/modules/`, `flow.md`, `claude_code.md`, `opencode.md`, `metrics.md` updated, `docs/reference/cli.md` regenerated, README explains shadow mode (bash and PowerShell).

## Out of scope

`ariane judge` and the report's shadow lines (later tickets of slice 4).

## Related

ADR 0030 (items 3, 4, 6), ADR 0017, ADR 0021, spec C19, "Adopting Ariane on an existing project".
