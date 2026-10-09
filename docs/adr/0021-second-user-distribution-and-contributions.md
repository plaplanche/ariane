# 0021. A second user: distribution, licence and outside fixes

- Status: accepted
- Date: 2026-10-08
- Capabilities: C22, C23, C24 (frozen)

## Context
A second user will run Ariane on macOS, on their own GitHub repository, with Claude Code.
Windows, macOS and Linux stay supported and the tracker interface stays. Distributing Ariane
raises the licence question (ADR 0008), and ADR 0008 forbids merging outside contributions
without a written agreement.

## Decision
- **Licence**: Ariane stays under `AGPL-3.0-only` (ADR 0008). The second user installs and
  runs it under that licence; nothing else is granted.
- **Outside fixes**: a fix found by the second user arrives as an issue (what fails, how to
  reproduce, the proposed change in words); no outside code is merged. Ariane implements the
  issue like any other. A contribution agreement is not offered for now.
- **Installation**: `uv tool install git+https://github.com/plaplanche/ariane` (the repository
  is public, so read access is open); the README gives every command in PowerShell and in
  bash, and a commented example `ariane.toml`.
- **What the user must know**: nobody runs git commands in the repository or pushes to it
  while a ticket runs (ADR 0017); the stop message says so too.

This decision complements ADR 0008.

## Consequences
The second user cannot send pull requests that get merged; their fixes cost an issue and a
ticket. A future change of mind (a contribution agreement, another licence) is a new ADR.

## Alternatives considered
- AGPL with a signed contribution agreement: accepts code, at the cost of an agreement to
  write and sign.
- Relicensing under Apache-2.0 or MIT before distribution: simpler contributions, but anyone
  could build a closed competitor (ADR 0008's reason).
