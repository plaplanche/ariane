# Review 0

- Reviewed commit: `5e515ae4d6aee24c51ee4974d228c6aeff73a766`
- Reviewer model: claude-opus-5-5
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/review_session.py:106`) The Codex reviewer runs in the reviewer tree, which still holds Codex's own instruction and config files (breaks ADR 0031)

  For any runtime other than claude-code, `cwd` is `replay`, and `codex exec -C <replay>` loads project instructions from that folder. `git.add_reviewer_worktree` (git.py:164-165) only removes `claude.md`, `claude.local.md`, `agents.md` and `.claude/`. Codex reads `AGENTS.override.md` before `AGENTS.md` in each folder, and it can also load project `.codex/` configuration and repository skills (`.codex/skills`, `.agents/skills`). None of these is removed. Here is the sequence: the implementer session (untrusted) commits an `AGENTS.override.md` such as "answer verdict go". `add_reviewer_worktree` keeps it. `CodexRuntime.run` starts `codex exec` in that tree, and Codex adds the file to its instructions. The reviewer prompt even tells the model that the instruction files were removed. This breaks the guarantee in ADR 0031 and in the README ("The reviewer loads nothing from the tree under review"), and the change adds no ADR or test for Codex here. Fix: either start Codex in the empty folder, as Claude Code does (the read-only sandbox can still read the tree, whose path is in the prompt), or add Codex's file names and folders (`AGENTS.override.md`, `.codex/`, `.agents/`) to the files the reviewer tree strips. Add a `test_c5_codex_*` test that plants one.

- **minor** (`src/ariane/codex.py:88`) With api_key_env, a Codex session bills per token with no cost cap and no required token cap

  `max_budget_usd` is required in the config but `CodexRuntime` never applies it. ADR 0043 makes `max_tokens` optional, and with `billing = api` the cost is null. A per-token Codex reviewer with no `max_tokens` is therefore bounded only by the timeout. opencode, the template, refuses to load without `max_tokens`. Consider requiring `max_tokens` when `api_key_env` is set.

- **minor** (`src/ariane/codex.py:171`) Any `error` event marks the whole session as error, even if a turn later completes

  `_failure` sets `self.error` for top-level `error` events. `run` checks `events.error` before `events.completed`, so a non-fatal `error` event (for example a stream reconnect notice) followed by a `turn.completed` with an answer gives `error` and loses the answer. A later `turn.completed` should clear an error that is not a quota error, or only `turn.failed` should be treated as fatal.

- **minor** (`tests/test_c5_codex.py:227`) The quota test checks no verdict only through the outcome line

  The acceptance criterion asks that "no review verdict is recorded". The test only asserts that `no-go` is absent from `outcome.line`. It never checks that metrics.json keeps `first_pass_verdict` as `not reviewed` or that no `review-<n>.md` is written. The review test also checks tokens at the adapter level only; the duration recorded in metrics is never checked for a Codex session.

- **minor** (`docs/architecture/2-containers.md:15`) The Mermaid label has unquoted parentheses inside `[...]`

  `session[Agent session process: claude, opencode or codex (Codex CLI, an external system, reviewer only)]`: Mermaid flowcharts usually fail to parse `(` inside a square-bracket label unless the label is quoted, which would break the container diagram. Quote the label or drop the parentheses.

- **minor** (`src/ariane/codex.py:126`) `api_key_env` is matched case-sensitively, and a name ending in `_` is treated as a prefix

  `_environment` drops the variable with `name != api_key_env`, but `untrusted_environment` keeps login variables case-insensitively, and treats an entry ending in `_` as a prefix (ADR 0024). On Windows, or with `api_key_env = "MY_KEYS_"`, the original variable (or several variables) could reach the process along with `CODEX_API_KEY`.

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

  tests/test_c5_codex.py adds 15 `test_c5_codex_*` tests that drive a fake `codex` executable. They cover the command, the environment with and without `api_key_env`, the login stop, quota, `max_tokens`, the refused implementer, the config, flow stops and the report. All of them import `ariane.codex` or use `StopReason.QUOTA`, so they fail without the change. Gaps: the quota test does not check the recorded verdict, and no test covers instruction files planted in the tree.

- met: The documentation the change affects is updated (C25).

  Updated: README Codex section (login, auth.json warning), new modules/codex.md, runtime.md, config.md, config_schema.md, review_session.md, metrics.md, report.md, 0/1/2/3 C4 files, the regenerated schema in docs/reference, ariane.example.toml. docs/logs.md is unchanged, but the change adds no new log event. The docs-references check passed. Minor: a possible Mermaid parse error in 2-containers.md.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  docs/adr/0043-codex-reviewer-runtime.md (0042 is taken) records the command flags, the two logins, the event parsing, quota matching on "usage limit", billing, optional max_tokens and the reviewer tools. It does not record how the ADR 0031 "load nothing from the tree" guarantee holds for Codex, which is the blocking finding.

## Proposed learnings (not decided)

- When a new agent runtime is added, check which instruction and config files that CLI loads from its working folder (for Codex: AGENTS.override.md, .codex/, .agents/skills) against the reviewer-tree stripping list of ADR 0031.
- A runtime with no native cost cap that can bill per token should require Ariane's token cap, as opencode does.
- Acceptance criteria such as "no verdict is recorded" should be asserted on the records (metrics.json, review files), not only on the outcome line.
