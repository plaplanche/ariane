# Review 2

- Reviewed commit: `6ba80943360e58176126ec45ff3c3a9bbd5106a4`
- Reviewer model: gpt-6-astra
- Verdict: **go**

## Findings

- **minor** (`README.md:105`) Document that stored credentials override api_key_env

  Setting api_key_env passes the selected key correctly, but does not necessarily switch the credentials pi uses. Pi 0.73.1 gives auth.json credentials priority over environment variables. Someone following the login instructions and then configuring api_key_env can therefore continue using the previous account. Document this precedence and the need to remove the provider's stored login when switching. Source: [pi 0.73.1 authentication documentation](https://raw.githubusercontent.com/badlogic/pi-mono/v0.73.1/packages/coding-agent/docs/providers.md).

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

  The new test_c5_pi tests exercise runtime selection, command flags, credential filtering, usage, caps, process-tree termination, delivery and guard violations; the base lacks the required runtime. Read-only parser and credential-filter assertions passed. Full-suite results are supplied by Ariane; I did not rerun tests that create files. Side-effect order inspected: snapshot before setup; setup/check writes followed by guard verification; reviewer-tree creation and instruction stripping; instruction/process/start logs; pi provider calls and possible login refresh; process cleanup; metrics and stopped-log writes; guard verification; only then verdict recording and delivery. Invalid-answer retries repeat the guarded session path.

- met: The documentation the change affects is updated (C25).

  README, configuration example, schema, architecture views and affected module documents are updated, including the new pi module document. The read-only generated-document check passed, including the unchanged log catalogue. One minor authentication-precedence clarification remains.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0051 records stdin transport and its verification, command flags, provider mapping, authentication, usage fields, cost and token enforcement, answer extraction and retry handling. The ADR 0031 amendment records additional guarded files and relative agent-directory resolution.

## Proposed learnings (not decided)

- Proposed: runtime authentication documentation should distinguish passing a credential from selecting it; stored-login precedence can override an explicitly configured environment key.
