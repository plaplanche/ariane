# Product brief: Slice 3 fix round: cap opencode sessions, ignore project opencode config, keep the reviewer read-only, bring the docs up to date (C5, C10, C21, C25)

- Source: issue #83 (https://github.com/plaplanche/ariane/issues/83)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

The end-of-slice review of slice 3 (independent, read-only, on a different model; CLAUDE.md rule 5) answered **NO-GO** with two blocking findings on the opencode reviewer, and the end-of-slice documentation review (rule 11, ADR 0022) found the module docs and the README behind the code. This issue is the slice's one fix round; a second review follows it. Spec: C5 (budget caps, vendors), C10 (review), C21 (credentials, untrusted text), C25 (documentation).

## Current state

1. **No enforced cap on opencode.** `src/ariane/opencode.py` stops a session on the cost reported in `step_finish` or on `max_tokens`. When the provider is priced at 0 (or not in opencode's price list), the cost is "not reported", and without `[agents.<role>].max_tokens` nothing caps the session but `steps` and the timeout. `config.py` `_opencode_agent` accepts such a configuration, and the journal still says "runtime cost cap 3 USD" (`review_session.py:91`), a cap opencode does not have.
2. **The implementer controls the reviewer's opencode configuration.** The reviewer runs in the replay tree, whose files the implementer wrote. Checked by the owner's session on opencode 1.18.35: an `opencode.json` or `.opencode/opencode.json` in that tree that sets `agent.ariane-reviewer.prompt` replaces the reviewer's prompt (`OPENCODE_CONFIG_CONTENT` wins only for the keys it sets). With `OPENCODE_DISABLE_PROJECT_CONFIG=1`, neither file is read and the inline configuration still applies.
3. **The reviewer may be given write tools on Claude Code.** `config.py` accepts `Write`, `Edit` or `Bash` for a Claude Code `[agents.reviewer]` (opencode agents are already limited to `read`, `glob`, `grep`); the read-only check covers only the replay tree.
4. **The reviewer's prompt states "all blocking ones green"** (`review.py`), which is false under `ariane verify` when a blocking check fails.
5. **Documentation** (end-of-slice review):
   - The "Collaborations" diagrams of 14 `docs/architecture/modules/*.md` miss callers that the imports show: `runtime.md` (cli, opencode, review_session, verify), `checks.md`, `config.md`, `tracker.md` (review, review_session, verify), `context.md` (review, verify), `review.md`, `ticket.md` (review_session, verify), `flow.md` (verify), `git.md`, `process.md`, `redact.md`, `review_session.md` (verify).
   - `README.md` "`ariane start` creates the branch …" says "one implementer session" and leaves out the review, the fix rounds, the draft pull request and the stop when blocking checks fail before any review.
   - `docs/architecture/README.md` does not list `review`, `review_session` and `verify` among the modules, and its level-3 row does not name the `ariane verify` sequence.
   - `1-context.md` shows only `ariane start`; `2-containers.md` omits `work/verify/<branch>/`, the log files in `<repo>.ariane/logs/` and the reviewer's read-only session; the `ariane start` sequence in `3-components.md` omits the stop before review when blocking checks fail.
   - "Serves": `runtime.md` misses ADR 0024 and ADR 0029; `ticket.md` misses C10.
   - `context.md` does not say that `untrusted_environment` sets `IS_SANDBOX=1`.
   - `README.md` status says "Measurement and approvals come next" (slice 4 is measurement and shadow, approvals are slice 5) and "capabilities C1 to C24" (the spec has C1 to C26).

## Decided spec

1. **Caps on opencode.** A configuration with `runtime = "opencode"` and no `max_tokens` is refused at load, naming `agents.<role>.max_tokens` ("opencode does not cap its own cost; Ariane needs a token cap"). Ariane's example `docs/ariane.opencode-reviewer.example.toml` sets one. For opencode sessions the journal says "runtime cost cap none; Ariane stops at <max_budget_usd> USD of reported cost or <max_tokens> tokens"; for Claude Code it keeps today's wording.
2. **No project configuration for the reviewer.** The opencode adapter always sets `OPENCODE_DISABLE_PROJECT_CONFIG=1`, next to `OPENCODE_DISABLE_CLAUDE_CODE=1`. ADR 0015 and ADR 0029 are amended with the probe above.
3. **Read-only reviewer.** On Claude Code, `[agents.reviewer].tools` is refused at load if it holds `Write`, `Edit`, `NotebookEdit` or `Bash`, naming `agents.reviewer.tools`.
4. **Prompt states the replay's result.** The reviewer's prompt says "all blocking checks green" only when they are; otherwise it lists the blocking checks that failed.
5. **Documentation.** Every point of "Current state" 5 is fixed, in the files named there.

## Release note

Fixed: the opencode reviewer always has a token cap and ignores project opencode configuration; a reviewer can no longer be given write tools; the architecture and README describe slice 3 as built.

## Acceptance criteria

- Tests named `test_c5_opencode_cap_*` show: an opencode agent without `max_tokens` is refused naming the key; an opencode session priced at 0 is stopped at `max_tokens` with stop reason `budget`; the journal entry names the caps that apply.
- Tests named `test_c21_opencode_project_config_*` show that `OPENCODE_DISABLE_PROJECT_CONFIG=1` is in every opencode session's environment.
- Tests named `test_c10_reviewer_read_only_*` show that each write tool listed above is refused for the reviewer, naming the key, and that the implementer may still have them.
- A test named `test_c10_review_prompt_failed_checks_*` shows the prompt names failed blocking checks instead of "all blocking checks green".
- All checks in CLAUDE.md pass.

## Acceptance checklist

- [ ] `uv run pytest -k "c5_opencode_cap or c21_opencode_project_config or c10_reviewer_read_only or c10_review_prompt_failed_checks"` runs at least 6 tests and they pass.
- [ ] All checks in CLAUDE.md pass.
- [ ] Definition of done, documentation (C25): every file named in "Current state" 5; ADR 0015 and ADR 0029 amended; `docs/ariane.opencode-reviewer.example.toml` sets `max_tokens`; `docs/reference/` and the log catalogue regenerated if they change.

## Related

#36, #81, ADR 0015, ADR 0022, ADR 0029, spec C5, C10, C21, C25.
