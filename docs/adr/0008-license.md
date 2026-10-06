# 0008. License

- Status: accepted
- Date: 2026-10-06
- Capabilities: none (project decision)

## Context
The repository becomes public so that GitHub can protect `main` (ADR 0007, layer 5), which
needs a license. The owner wants Ariane to be open source while keeping the option of a
commercial activity around it later.

## Decision
- Ariane is licensed under the GNU Affero General Public License, version 3 only
  (`AGPL-3.0-only`), full text in `LICENSE`, declared in `pyproject.toml`.
- "Only" rather than "or later": the license terms stay the ones chosen here; a future version
  published by the Free Software Foundation does not apply unless the owner decides it.
- The owner, as copyright holder, can also grant other terms (for example a commercial license)
  alongside the AGPL. To keep that possible, a contribution from anyone else is accepted only
  with a written agreement giving the owner the right to relicense it; until such an agreement
  exists, outside contributions are not merged.

## Consequences
Anyone can use, study, modify and share Ariane. Anyone who offers a modified Ariane to others,
including as a network service, must publish their source under the same license, so a
competitor cannot turn it into a closed hosted product. Some companies avoid AGPL software; they
can ask for other terms.

## Alternatives considered
- Apache-2.0 or MIT: maximal adoption, but anyone may build a closed or hosted competitor.
- Functional Source License: protects a future product best, but is not open source.
- Staying private: GitHub protects branches of private repositories only on paid plans.
