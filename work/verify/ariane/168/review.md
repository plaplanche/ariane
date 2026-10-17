# Review 0

- Reviewed commit: `964e75b15a0dce0bea7ee0efa43c1ff1d212da5c`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/context.py:186`) Credential-bearing proxy URLs pass without declaration

  The issue and ADR 0024 say a proxy URL containing credentials must be declared by the project. However, every proxy variable passes through BASE_VARIABLES without inspecting its value. A read-only reproduction with env=[] and HTTPS_PROXY=http://***@proxy:3128 confirmed that the complete credential-bearing URL passes and produces no declared-secret warning. In start, this environment reaches setup before ticket-folder creation and journal writes, then reaches implementer sessions and check replay; verify also supplies it to setup and checks. No declaration check guards those subprocess launches. Require explicit declaration for credential-bearing proxy URLs and add regression tests covering undeclared rejection and declared acceptance.

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

  The new tests exercise allow-list filtering, declarations, extended redaction patterns and schema validation, which the previous implementation lacks. Nine acceptance test functions passed when invoked directly without filesystem-writing fixtures. Ariane reports the full suite passed. Credential-bearing proxies remain untested.

- met: The documentation the change affects is updated (C25).

  README, example and project configuration, affected module documentation, schema reference and log catalogue are updated. The proxy behavior contradicts the updated ADR, as reported above.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0024's amendment records matching semantics, secret-pattern boundaries, warning severity, verify's journal exception and restoration of git identity variables for Ariane's commits.

## Proposed learnings (not decided)

- Proposed: Test credential-bearing values in otherwise allowed variables; a name-based allow list alone cannot enforce value-dependent exceptions.
