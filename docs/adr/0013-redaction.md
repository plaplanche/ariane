# 0013. Redaction of everything Ariane publishes

- Status: accepted
- Date: 2026-10-07
- Capabilities: C21 (basic)

## Context
C21: every published output (comments, attachments, logs) is filtered for known secrets and
common token formats before posting. Slice 1 masks the tracker token in the ticket folder only.
The ticket folder is pushed, so it is published too.

## Decision
One function `redact(text, known)` replaces with `***`:
- every known secret value (the tracker token, and any environment variable whose name marks a
  credential, as already stripped from agents, ADR 0007), when at least 8 characters long;
- common token formats: GitHub (`ghp_`, `gho_`, `ghu_`, `ghs_`, `ghr_`, `github_pat_`),
  Anthropic (`sk-ant-`), OpenAI-style (`sk-` followed by 20 or more characters), AWS access keys
  (`AKIA` + 16), Slack (`xox[abprs]-`), private key blocks (`-----BEGIN ... PRIVATE KEY-----` to
  the matching end), and URL credentials (`scheme://user:pass@`).

It is applied to: every text Ariane sends to the tracker (pull request title and body, comments,
status descriptions) and every file it writes to the ticket folder.

## Consequences
A false positive masks harmless text; a secret in an unknown format still gets through (forbidden
terms and the security review are slice 7).

## Alternatives considered
- An external scanner (gitleaks, trufflehog): a dependency and a binary to install on three OS.
