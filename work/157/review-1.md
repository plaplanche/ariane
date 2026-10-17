# Review 1

- Reviewed commit: `0c841446ddfb055f7c6117e399d42287e6ab98aa`
- Reviewer model: claude-opus-5-5
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/codex.py:47`) Any CLI login without api_key_env is recorded as plan billing with cost 0, including an API-key login

  The decided spec says cost_usd is 0 and billing is "plan" only "when the CLI is logged in with a ChatGPT account (no api_key_env)". `billing` returns PLAN whenever `api_key_env` is None. `logged_in` (line 80-88) only checks that the `codex login status` output does not contain "not logged in". A CLI logged in with `codex login --with-api-key` (status: "Logged in using an API key ...") therefore passes the check. Every session then bills per token, but metrics.json records `cost_usd: 0` and `billing: "plan"`, the journal says "Billing: covered by the plan", and `ariane report` shows "covered by plan". This is exactly the silent per-token spend the ticket wants to rule out, and it corrupts the C19 cost metrics the #130 benchmark depends on. The status output already tells the two cases apart ("Logged in using ChatGPT"). Fix: take plan billing only when the status says ChatGPT, and otherwise record `api` with a null cost (or stop the ticket). Add a test with the fake CLI printing an API-key login status.

- **minor** (`src/ariane/codex.py:88`) Any non-zero exit of `codex login status` is reported as "not logged in"

  `done.ok and ...` treats a crash, a timeout or a config error of `codex login status` as a missing login. The ticket then stops with the login message, which is misleading. Consider keying only on the "Not logged in" text and reporting other failures as errors with their output.

- **minor** (`src/ariane/codex.py:125`) api_key_env naming an unset or empty variable silently falls back to the CLI's stored login

  If the named variable is missing, `key` is None, so no CODEX_API_KEY is set and no login check runs. Codex then uses whatever is in auth.json, while the session is labelled `billing: api`. A config-time or run-time error ("agents.reviewer.api_key_env: variable X is not set") would be clearer.

- **minor** (`README.md:56`) `tools` for a Codex reviewer is accepted but has no effect

  The README and ADR say a Codex reviewer's tools follow the Read/Glob/Grep allow list. `codex exec` never receives them, though: the reviewer can run arbitrary shell commands, limited only by the read-only sandbox (the fixture even shows `command_execution`). The docs should say that the sandbox, not `tools`, is the restriction, so the owner is not misled about what the reviewer can do.

- **minor** (`tests/test_c5_codex.py:214`) Quota and login ticket-level tests use a fake runtime, not the fake CLI

  The flow-level quota and not-logged-in tests use QuotaReviewer/LoggedOutReviewer instead of CodexRuntime driving fake_codex.py. Session-level tests cover the CLI path, so the chain is covered piece by piece but not end to end as the acceptance criteria describe.

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

  tests/test_c5_codex.py has 19 test_c5_codex_* tests, using fake_codex.py on recorded JSON Lines fixtures. They cover: the answer and usage, argv (read-only sandbox, model, stdin prompt), environment stripping and CODEX_API_KEY, not logged in, quota, max_tokens, implementer refusal, the report's "covered by plan", and reviewer-tree stripping. None of them can pass without the new code. The plan/API-key login distinction is not tested (blocking finding).

- met: The documentation the change affects is updated (C25).

  New: docs/architecture/modules/codex.md. Updated: runtime.md, config.md, config_schema.md, review_session.md, metrics.md, report.md, git.md, process.md, cli.md, the 0-3 C4 files (Codex CLI as an external system in 2-containers.md), docs/reference/ariane.toml.schema.json regenerated (the docs: references check passes), docs/ariane.example.toml, and the README section with codex login and the warning to keep auth.json private. docs/logs.md is unchanged because no new log event was added.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  docs/adr/0043-codex-reviewer-runtime.md (0042 was already taken) records: the exact flags checked with codex exec --help, the two login modes, environment stripping, the extra instruction files stripped from the reviewer tree, the event parsing, quota matching on "usage limit", max_tokens being required only with api_key_env, the tools allow list, and the billing values.

## Proposed learnings (not decided)

- A billing label derived from configuration (api_key_env set or not) can disagree with how the CLI is actually authenticated; derive it from what the runtime reports (`codex login status`), not from Ariane's config alone.
- For runtimes whose sandbox, not a tool allow list, is the real restriction, the docs should say so rather than reuse the allow-list wording of another runtime.
