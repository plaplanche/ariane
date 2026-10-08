# Product brief: Redact known secrets and common token formats in everything Ariane publishes (C21 basic)

- Status: draft
- Approved: not yet
- Source: issue #19 (https://github.com/plaplanche/ariane/issues/19)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

C21 (basic, slice 2): every published output is filtered for known secrets and common token formats before posting. Ariane publishes pull request titles and bodies, commit status descriptions, and the ticket folder (pushed with the branch). Today only the tracker token is masked, and only in the ticket folder. Decision: ADR 0013.

## Current state

- `src/ariane/ticket.py:108` `TicketFolder._redact` replaces the known secrets given to the folder (the tracker token) with `***`.
- `src/ariane/git.py:35` `redact` hides `scheme://user:pass@` credentials in git error messages.
- `src/ariane/delivery.py` sends the pull request title and body and the status descriptions to the tracker without redaction.
- `src/ariane/context.py` `untrusted_environment` already knows which environment variables carry credentials.

## Decided spec

A new module `src/ariane/redact.py` with one function `redact(text, known)` that returns `text` with these replaced by `***`:

- every value in `known` that is at least 8 characters long (shorter values are ignored, to avoid masking common words);
- GitHub tokens: `ghp_`, `gho_`, `ghu_`, `ghs_`, `ghr_` followed by 30 or more letters, digits or underscores, and `github_pat_` followed by 20 or more of them;
- Anthropic keys: `sk-ant-` followed by 20 or more letters, digits, `-` or `_`;
- other `sk-` keys: `sk-` followed by 20 or more letters, digits, `-` or `_`;
- AWS access key ids: `AKIA` followed by exactly 16 uppercase letters or digits;
- Slack tokens: `xoxa-`, `xoxb-`, `xoxp-`, `xoxr-`, `xoxs-` followed by 10 or more letters, digits or `-`;
- private key blocks: from `-----BEGIN ` ... `PRIVATE KEY-----` to the matching `-----END ... PRIVATE KEY-----`, whole block;
- URL credentials: `scheme://user:pass@` becomes `scheme://***@` (the current `git.redact` behaviour).

The known secrets are the tracker token plus the value of every environment variable whose name `untrusted_environment` treats as a credential.

Apply it to:
- everything the ticket folder writes (replacing `TicketFolder._redact`);
- the pull request title and body and each commit status description, just before they are sent to the tracker;
- `git.redact` callers (git errors), which then use `redact.py`.

## Release note

Security: Ariane masks known secrets and common token formats in everything it publishes.

## Acceptance criteria

- Tests named `test_c21_redact_*` in `tests/test_redact.py` cover: each token format above (one positive example each), a known secret of 8 or more characters, a known value shorter than 8 characters left untouched, a private key block masked whole, a URL credential, and ordinary text (for example a commit SHA, a UUID and the word `skeleton`) left untouched.
- A flow test named `test_c21_redact_published_*` shows that a GitHub token placed in the issue title, the agent's summary and a check's output reaches neither the tracker (pull request title and body, status descriptions, read from InMemoryTracker) nor any file of the ticket folder on the pushed branch.
- All checks in CLAUDE.md pass.

## Acceptance checklist

- [ ] `src/ariane/redact.py` exists and `TicketFolder` uses it.
- [ ] `uv run pytest -k c21_redact` runs at least 8 tests and they pass.
- [ ] All checks in CLAUDE.md pass.

## Out of scope

Forbidden terms and the security review (slice 7), redaction of anything Ariane does not publish (its console output).

## Related

ADR 0013, ADR 0007 (untrusted environment).
