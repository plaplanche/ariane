# Review 0

- Reviewed commit: `29190f104bfc1a22ba6f838c6084e41f07daf2eb`
- Reviewer model: claude-opus-5-5
- Verdict: **go**

## Findings

- **minor** (`src/ariane/github.py:135`) Transient permission-endpoint failures now count as refusals (exit 2) instead of tracker errors (exit 1)

  Any error from the permissions endpoint other than 404 now raises IssueRefused. That includes a rate-limit 403/429, a 5xx and a network timeout, so the command exits 2 and says the issue is not trusted. A temporary GitHub outage looks the same as a security refusal, and the suggested fix (add the label again) will not help. `GET /repos/{repo}` failing is still a TrackerError (exit 1), so the two endpoints handle errors differently. This fails closed, so it is safe, and the ADR amendment documents it. A later ticket could keep exit 1 for 5xx and network errors and refuse only on 401/403.

- **minor** (`docs/adr/0032-issue-gate.md:1`) ADR title and Consequences still describe the superseded rule

  The title still says "not edited by anyone else since". Consequences still say "three to four requests per run" and "after any later edit by someone else". The status line and the amendment make clear they are superseded, which is acceptable for an ADR. A reader who skims only the header and Consequences will still get the wrong rule.

- **minor** (`src/ariane/github.py:19`) 1 s slack deviates from the 5 s the commit message cites from the issue

  The first commit message says 'within 5 s of the last label', and the fix commit narrows it to 1 s. That is stricter and safer, the ADR amendment records it, and tests cover it (accepted at +1 s, refused at +2 s). The owner should still know the value differs from what the ticket asked. Also, updated_at may sometimes be stamped one second after the label event because of clock skew between GitHub services. That would give a refusal that only another label fixes. The fix is clear, so this is not a safety issue.

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

  tests/test_c21_issue_gate.py adds these tests: refused when changed after the label (AFTER and +2 s); accepted within the 1 s slack; owner of a user repository trusted without a permission call, even when the permission endpoint answers 403 and no /graphql call is made; owner login compared without case, with the repository read once across two read_issue calls; an organisation owner's login not trusted; a 403 from the permission endpoint refused with the user's name. The 403-owner test, the updated_at tests and the 403-refusal test fail against the base code, which called GraphQL and the permission endpoint and ignored updated_at. tests/test_github.py stubs are updated for the new requests.

- met: The documentation the change affects is updated (C25).

  README.md:72-76, docs/ariane.example.toml:18, docs/architecture/modules/github.md:7 and docs/architecture/modules/flow.md:11 now describe the REST-only gate. That fixes the flow.md gap the earlier review found. ADR 0032 has an amendment and an updated status. verify.md, tracker.md, cli.md and config.md stay accurate. docs/reference has no stale GraphQL or 'edited' wording, and the docs: references check passes.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  The ADR 0032 amendment (docs/adr/0032-issue-gate.md:38-59) records each open choice: the owner of a user repository is trusted from GET /repos/{repo} with logins compared without case; errors other than 404 refuse; the 1 s slack on updated_at and why; GraphQL and the renamed check are removed; the residual risk of a body edit within the second after the label; Ariane's own cross-reference needing the label again; GET /repos failures are exit 1; organisations still use the permissions endpoint.

## Proposed learnings (not decided)

- When a REST-only check uses `updated_at` as a catch-all change detector, record the residual window it cannot see (here, body edits within the slack) as an accepted risk in the ADR.
- Any change after the label refuses, so Ariane's own activity on the issue (a PR cross-reference from 'Closes #N') makes a later `ariane verify --issue N` need the label again. Hand takeovers should plan for that.
- Mapping every non-404 error from an authorization endpoint to a refusal fails closed but merges transient outages with security refusals. Keep the exit-code meaning in mind when choosing error classes.
