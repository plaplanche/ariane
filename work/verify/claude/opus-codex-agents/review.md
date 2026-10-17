# Review 0

- Reviewed commit: `ec411a7fa41a31e2be0ad5a064c7739b08dce413`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`ariane.toml:21`) Omitting api_key_env does not guarantee plan billing

  With a stored API-key login, CodexRuntime.run removes environment keys, calls login status, accepts its 'api' result, then launches codex exec and incurs per-token charges. No ChatGPT-only guard precedes that external call. This configuration also omits max_tokens, and the runtime does not enforce max_budget_usd. The existing test_c5_codex_an_api_key_login_is_billed_per_token_not_by_plan explicitly confirms this path. Enforce a plan-only login before launching the reviewer to meet ADR 0044's billing promise.

- **blocking** (`tests/test_config.py:184`) Tests do not protect the configuration change

  The modified helper replaces whichever reviewer model exists, and the schema test explicitly substitutes Claude settings. Both remain valid with the old repository configuration. No added assertion requires the Opus implementer, its 10 USD budget, or the Codex gpt-6-astra reviewer without api_key_env. Add a regression test that fails when these settings are reverted, plus coverage that a stored API-key login cannot start the intended plan-only reviewer.

- **blocking** Definition of done not met: The change is covered by tests that fail without it.

  The two test edits remove assumptions about the repository configuration; neither asserts the new configuration. Ariane's reported green checks establish compatibility, not regression coverage.

- **blocking** Definition of done not met: The documentation the change affects is updated (C25).

  ADR 0044 and configuration comments document the switch, but their plan-only billing guarantee contradicts the runtime's accepted stored API-key login path.

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

- **not met**: The change is covered by tests that fail without it.

  The two test edits remove assumptions about the repository configuration; neither asserts the new configuration. Ariane's reported green checks establish compatibility, not regression coverage.

- **not met**: The documentation the change affects is updated (C25).

  ADR 0044 and configuration comments document the switch, but their plan-only billing guarantee contradicts the runtime's accepted stored API-key login path.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0044 records the implementer model and budget, reviewer runtime and model, intended authentication mode, prerequisites, and alternatives.

## Proposed learnings (not decided)

- Removing credential environment variables does not exclude credentials stored by a CLI.
- Configuration changes need assertions on the intended settings; making existing tests configuration-independent does not protect the new behavior.
