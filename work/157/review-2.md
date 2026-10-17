# Review 2

- Reviewed commit: `6137617829b79f039047ab12f2c2161060ae245f`
- Reviewer model: claude-opus-5-5
- Verdict: **go**

## Findings

- **minor** (`src/ariane/codex.py:108`) An API-key login stored by the CLI runs per-token with no token cap

  Without api_key_env, `codex login status` can report an API-key login. The code then sets billing to `api` and starts the session. The config only requires `max_tokens` when `api_key_env` is set (config.py), so this per-token session can run with no cap at all. ADR 0043 gives the reason for the rule as "a per-token session has no cost cap, so Ariane needs a token cap", and this path skips it. Two fixes would close it: refuse to start when the login is `api` and `max_tokens` is None, or record this case in the ADR.

- **minor** (`src/ariane/codex.py:33`) Only `OPENAI_*` and `CODEX_API_KEY` are stripped

  The spec asks to remove "any other OpenAI key variable". In practice `untrusted_environment` already drops names that match `_SECRET_NAME` (for example `AZURE_OPENAI_API_KEY`). The codex-specific list is still narrower than the wording, though, and the test only covers `OPENAI_*` and `CODEX_API_KEY`.

- **minor** (`src/ariane/codex.py:91`) Output of a failed `codex login status` goes into the journal

  When `codex login status` exits non-zero without saying "not logged in", its output tail becomes the session summary and the journal. The fake CLI prints `Logged in using an API key - sk-...` for an API-key login. If a real CLI ever printed part of a key on a failing status, it would be logged, which goes against "never logs any token". Ariane's redaction of known secrets probably covers the full value but not a fragment. Low risk, since the real CLI masks the key.

- **minor** (`src/ariane/codex.py:226`) `reasoning_output_tokens` is ignored

  Usage sums `output_tokens` only. If Codex counts reasoning tokens separately from `output_tokens`, the recorded tokens and the `max_tokens` cap undercount. The ADR records that cached tokens are inside `input_tokens` but says nothing about reasoning tokens. It is worth one sentence in ADR 0043.

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

  tests/test_c5_codex.py adds 22 `test_c5_codex_*` tests. They import the new `ariane.codex`, `StopReason.QUOTA`, `SessionResult.billing`/`next_step` and `report.COVERED`, and they drive a fake `codex` (tests/fake_codex.py) with recorded JSON Lines. They cover the acceptance criteria: a review answered with tokens and duration; the read-only command with the prompt on stdin; the environment with and without api_key_env; not logged in at session and flow level; a quota stop at session and flow level with no review-*.md and NOT_REVIEWED; max_tokens as budget; the implementer refused; the report showing "covered by plan". None of them can pass on the base commit.

- met: The documentation the change affects is updated (C25).

  The diff adds the new docs/architecture/modules/codex.md and updates runtime.md, config.md, config_schema.md, review_session.md, metrics.md, report.md, git.md, cli.md and process.md. It also updates 0-landscape, 1-context, 2-containers (Codex CLI shown as an external system, reviewer only), 3-components and the architecture README. The generated docs/reference/ariane.toml.schema.json is regenerated, and the docs: references check passes. docs/ariane.example.toml and the README's "Reviewer on Codex" paragraph (codex login, keep auth.json private) are updated. No new log event is added, so docs/logs.md does not change.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  docs/adr/0043-codex-reviewer-runtime.md records these choices: the exact flags (checked on codex-cli 0.163.0); `tools` being ignored; `max_tokens` required with api_key_env; how `login status` is read; how key variable names are matched; stripping of .codex/.agents/AGENTS.override.md; event handling, including a reconnect notice cleared by a later turn; the quota match on "usage limit"; billing; and the alternatives considered. 0042 is already taken (`not_run_locally`), so 0043 is the next free number.

## Proposed learnings (not decided)

- When a runtime can bill per token through more than one path (a configured key, or a key the CLI stored itself), check that every per-token path gets the same token-cap guard, not only the configured one.
- For a new reviewer runtime, check that the review tree also drops that runtime's own instruction and config folders (here AGENTS.override.md, .codex/, .agents/), not only Claude's.
