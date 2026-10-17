# Review 0

- Reviewed commit: `17b29be6b550b7dc4f98d023840fe3acb17b5e9d`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/context.py:149`) Declared proxy credentials escape redaction

  Credential-bearing proxies are classified as declared secrets here, but known_secrets omits their values. Reproduced read-only with HTTPS_PROXY=user:long-proxy-password@proxy:3128 declared in project.env: it passes, the journal names HTTPS_PROXY, known_secrets returns [], and redact preserves the complete credential. The existing URL redactor requires ://, whereas this change explicitly supports scheme-less proxies. The affected sequence is: setup/check receives the declared proxy; its output includes the value; TicketFolder.write redacts using the incomplete secret list and writes checks.md; git.commit records it; delivery pushes it. Verify likewise writes and commits the unmasked report. Include credential-bearing proxy values in known_secrets and add a regression test covering recorded output, including scheme-less values.

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

  Twelve test_c21_env_allow_list_* tests cover filtering, declarations, journal entries, extended secret patterns, schema validation and proxies. The new configuration and filtering assertions fail against the previous implementation. Ariane reports the suite passed; independent pytest execution was unavailable because the installed Python lacks pytest. Proxy-output redaction remains uncovered, as reported above.

- met: The documentation the change affects is updated (C25).

  README, example configuration, affected module documentation, generated schema and log catalogue are updated. Ariane reports the generated-reference check passed.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0024 records the allow list, declaration matching, credential-bearing proxy handling, secret-pattern boundaries, commit identity restoration, warning severity and verify logging behavior.

## Proposed learnings (not decided)

- Proposed: whenever a new path deliberately passes a secret, test its complete journey through captured output, redaction and persisted records.
