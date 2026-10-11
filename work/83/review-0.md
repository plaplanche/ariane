# Review 0

- Reviewed commit: `ed83163e4d3837eb72ff70fb061080b2e9eb8e08`
- Reviewer model: claude-opus-5-5
- Verdict: **go**

## Findings

- **minor** (`src/ariane/config.py:266`) Reviewer write-tool check matches exact names only

  The check compares tool names exactly against Write/Edit/NotebookEdit/Bash. A scoped entry such as "Bash(git:*)", or another writing tool such as MultiEdit, is not refused. This meets the ticket as written, but a prefix match on "Bash(" and a broader deny list would make the read-only guarantee stronger.

- **minor** (`docs/architecture/modules/opencode.md:5`) Environment bullet still lists the old variables

  The intro paragraph now names OPENCODE_DISABLE_PROJECT_CONFIG=1, but the first bullet ('The environment adds OPENCODE_CONFIG_CONTENT …, OPENCODE_DISABLE_CLAUDE_CODE=1 and OPENCODE_DISABLE_AUTOUPDATE=1') leaves it out. The module doc now partly contradicts itself.

- **minor** (`tests/test_c5_opencode.py:333`) Zero-price cap test probably passed before the change

  test_c5_opencode_cap_a_session_priced_at_zero_stops_at_max_tokens exercises the max_tokens stop, which already existed in opencode.py. It documents the behaviour but does not fail without this diff. The other new tests (refused at load, journal text, env var, read-only tools, prompt) do fail without it.

- **minor** (`README.md:11`) Line wrapping in README status sentence

  The edited status line and the 'ariane start' paragraph go past the file's usual wrap width. This is cosmetic only.

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

  These tests fail without the change: test_c5_opencode_cap_an_agent_without_max_tokens_is_refused (new load-time refusal), test_c5_opencode_cap_the_journal_names_the_caps_that_apply (new cap_text), test_c21_opencode_project_config_is_disabled_in_every_session (new env var), test_c10_reviewer_read_only_write_tools_are_refused (4 parametrized cases, also showing the implementer keeps the tools) and test_c10_review_prompt_failed_checks_are_named. That is at least 6 tests matching the -k filter. Ariane's replay shows the tests check passing.

- met: The documentation the change affects is updated (C25).

  These are updated: the Collaborations diagrams of runtime, checks, config, tracker, context, review, ticket, flow, git, process, redact and review_session, which match the imports in src/ariane. Also README (the start sequence, the status line and C1 to C26), architecture/README (review, review_session and verify modules, and the level-3 row), 1-context (verify), 2-containers (verify records, logs, read-only reviewer) and the 3-components stop-before-review. The Serves lines are fixed (runtime has ADR 0024 and 0029, ticket has C10), and context.md now mentions IS_SANDBOX. ADR 0015 and ADR 0029 are amended, and the example toml sets max_tokens. The docs: references check passed. One minor gap: a bullet in opencode.md.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  The ticket decided every behaviour. The new constraints (max_tokens required, project config disabled, forbidden reviewer tools) are recorded as amendments to ADR 0015 and ADR 0029. No other open choice was introduced.

## Proposed learnings (not decided)

- When a doc paragraph is amended, check the bullets below it for an older list of the same items (opencode.md env vars).
- A deny list of tool names should consider scoped forms like Bash(...) as well as exact names.
- A test named for a fix should fail without the fix; tests of behaviour that already existed should be labelled as regression coverage.
