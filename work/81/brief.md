# Product brief: Pass the opencode prompt on standard input, give each role its own environment, make verify's records reliable (C5, C21, C23)

- Source: issue #81 (https://github.com/plaplanche/ariane/issues/81)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

Slice 3's tickets are delivered (#33, #34, #35, #36). Their reviews left points that would make slice 3's gate fail or that widen what an agent can reach. This issue fixes them before the gate. Spec: C5 (agent runtime), C10 (review), C21 (credentials), C23 (`ariane verify`), C25 (documentation).

## Current state

- `src/ariane/opencode.py`: the prompt is passed as the last argument of `opencode run`. `_too_long` ends the session with `error` above `WINDOWS_COMMAND_LIMIT` (32,000 characters for the whole command line) or `POSIX_ARGUMENT_LIMIT` (127 KiB per argument). A review prompt holds the issue and the diff (up to `review.MAX_DIFF_CHARS`, 200,000), so most real tickets exceed it and the opencode reviewer cannot review them.
- `src/ariane/runtime.py` `RoutedRuntime.login_variables` is the union of every runtime's variables; `flow.py` and `verify.py` build one `agent_env` from it. With the reviewer on opencode, the Claude Code implementer (which has Bash and reads untrusted issue text) also receives the reviewer's provider key, and the reviewer receives `ANTHROPIC_*`/`CLAUDE_*`.
- `src/ariane/verify.py`: `git.commit`'s result is ignored, so the output says "Records committed on the branch" and can exit 0 when nothing was committed (for example when the project's `.gitignore` covers `work/`). The checks on where the branch is checked out and whether that tree is clean run only at the start; the commit happens minutes later.
- `docs/architecture/modules/process.md` does not name `opencode` among its callers nor `_shown` (arguments cut to 200 characters in the `process.started` log line).
- No test covers `cli._runtime` choosing `OpenCodeRuntime` for a reviewer with `runtime = "opencode"`.

## Decided spec

1. **Prompt on standard input.** Checked by the owner's session on opencode 1.18.35: with no message argument, `opencode run` reads the message from standard input; a 300,000-character message piped in reached the model whole (the title request and the first step both carried it). The adapter passes the prompt as `input_text`, as the Claude Code adapter does, and no longer as an argument. `_too_long`, `WINDOWS_COMMAND_LIMIT` and `POSIX_ARGUMENT_LIMIT` are removed; the `OSError` handling stays. ADR 0029 is amended.
2. **One environment per role.** Each session gets an environment built from its own role's runtime `login_variables` (`RoutedRuntime.for_role(role).login_variables`), in `flow.py`, `review_session.py` and `verify.py`. The union disappears; `RoutedRuntime` keeps `name` for the journal. The checks' environment is unchanged (no login variable).
3. **`verify` commits or says it did not.** When `git.commit` commits nothing, `verify` exits 1 with "nothing was recorded: <reason>" and the next action "check that work/ is not ignored, then run verify again". Just before committing, it checks again where the branch is checked out and that this tree is clean; if either changed since the start, it exits 1 naming what changed, without committing.
4. **Documentation and test.** `modules/process.md` names `opencode` and the 200-character cut of `process.started`. A test shows `cli._runtime` builds an `OpenCodeRuntime` with the configured model for a reviewer on opencode.

## Release note

Fixed: the opencode reviewer takes prompts of any size; each agent session gets only its own runtime's login; `ariane verify` no longer reports records it did not commit.

## Acceptance criteria

- Tests named `test_c5_opencode_stdin_*` show: the command has no message argument; the prompt is given as `input_text`; a 300,000-character prompt runs (with the fake executable) and is not cut.
- Tests named `test_c21_role_env_*` show: with the reviewer on opencode declaring `OPENAI_API_KEY`, the implementer's and fix sessions' environments do not hold it and the reviewer's does; the reviewer's does not hold `ANTHROPIC_*`/`CLAUDE_*`.
- Tests named `test_c23_verify_records_*` show: a project ignoring `work/` gets exit 1 and "nothing was recorded"; a branch committed to, or checked out elsewhere, during the run gets exit 1 and nothing committed.
- A test named `test_c5_opencode_cli_runtime_*` covers `cli._runtime`.
- All checks in CLAUDE.md pass.

## Acceptance checklist

- [ ] `uv run pytest -k "c5_opencode_stdin or c21_role_env or c23_verify_records or c5_opencode_cli_runtime"` runs at least 7 tests and they pass.
- [ ] `src/ariane/opencode.py` has no command-length limit.
- [ ] All checks in CLAUDE.md pass.
- [ ] Definition of done, documentation (C25): ADR 0029 amended (standard input, environment per role); `docs/architecture/modules/opencode.md`, `runtime.md`, `flow.md`, `review_session.md`, `verify.md` and `process.md` updated; the log catalogue and `docs/reference/` regenerated if they change.

## Out of scope

opencode for the implementer role; the review findings marked minor on #77 (`context._escape` made public, mid-segment `**/`).

## Related

#36, #35, ADR 0015, ADR 0029, spec C5, C10, C21, C23, C25.
