# Review 0

- Reviewed commit: `5ebe6ed80898b01a8529c5a711bddcf6492e8718`
- Reviewer model: claude-opus-5-5
- Verdict: **go**

## Findings

- **minor** (`docs/adr/0043-codex-reviewer-runtime.md:13`) The Decision section still says an API-key login is billed per token

  Line 13 still says "a status that does not say ChatGPT (an API-key login) is billed per token (`api`, cost null)". The amendment on line 20 says it "replaces the earlier rule", so the ADR is consistent overall. Still, someone who reads only the Decision bullets gets the old behaviour. A short note on line 13 pointing to the amendment would fix this.

- **minor** (`src/ariane/codex.py:97`) Any login that is not ChatGPT is reported as an API-key login

  `login()` maps every successful status that does not mention "chatgpt" to `api`. `run()` then stops with "Codex is logged in with an API key, not ChatGPT". This is fail-safe and matches the spec ("logged in but not with ChatGPT"). But if a future CLI wording drops the word "ChatGPT", a real plan login would be reported as an API-key login. That is a wrong message, not a per-token bill, so it is not blocking.

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

  `tests/test_c5_codex.py:134` (`test_c5_codex_plan_only_an_api_key_login_without_api_key_env_does_not_start`): with the fake `codex` reporting an API-key login, `seen == {}`, so `codex exec` never ran. It checks the exact summary and next step and `structured_output is None`. Before this change the session ran with `billing api`, so this test would fail. `test_c5_codex_plan_only_an_api_key_login_ends_the_ticket_without_a_verdict` runs `flow.start` end to end. It asserts a non-zero exit, the stop message and next step in the line, no "no-go", and `first_pass_verdict == NOT_REVIEWED` in metrics.json. Two more tests cover the unchanged paths: `..._a_chatgpt_login_runs_on_the_plan` (`billing plan`, cost 0) and `..._api_key_env_still_runs_per_token` (`billing api`, cost None, with an API-key login). The old `test_c5_codex_an_api_key_login_is_billed_per_token_not_by_plan` is gone. That makes 4 `c5_codex_plan_only` tests, at least the 3 the ticket asks for.

- met: The documentation the change affects is updated (C25).

  `docs/architecture/modules/codex.md`: new `API_LOGIN` and `API_LOGIN_NEXT` constants, a behaviour bullet, updated billing text, and a new flowchart branch. The README's "Reviewer on Codex" section (lines 65-68) now says the CLI must be logged in with ChatGPT and what happens otherwise. `docs/logs.md` has no Codex entry, and no log line was added or changed, so it did not need regenerating.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  The ticket fixes the behaviour and the message word for word. The only design change is recorded as the amendment in `docs/adr/0043-codex-reviewer-runtime.md` (line 19-20, "Amendment (#178)"), with the reason (usage arrives at the end of a turn). The change leaves no other choice open.

## Proposed learnings (not decided)

- When an ADR is amended, also edit or point from the original Decision bullet that the amendment replaces, so that reading only the Decision section is not misleading.
- For 'does not start' guarantees, the fake CLI's dump file being absent (`seen == {}`) shows that no `codex exec` process ran; reuse this pattern for other pre-run checks.
