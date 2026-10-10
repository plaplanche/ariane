# 0026. Documentation upkeep choices

- Status: accepted
- Date: 2026-10-10
- Capabilities: C25

## Context
ADR 0022 asks projects to declare their documentation. The ticket for C25 fixes the `[documentation]` table; a few details were left open.

## Decision
- A `source` glob is matched against the whole repository-relative path: `*` and `?` stay within a path segment, `**` crosses segments.
- A mapped document that is a folder counts as updated when any file under it changed.
- Each `generated` entry becomes a blocking check named `docs: <name>` with a 15-minute timeout, run after the declared checks in the replay with the same credential-free environment. Names must be unique.
- The untouched documents are computed from the paths the agent changed, `work/` excluded, once the agent's work is committed; they are journaled and given to the reviewer as a fact. They never stop the ticket.

## Consequences
The reviewer sees the generated checks in its checks table. `paths` is only loaded for now (used by `ariane docs-review`, slice 6).

## Alternatives considered
- `fnmatch` semantics (`*` crossing folders): rejected, `{stem}` would then be wrong for nested files.
- A configurable timeout for generated checks: rejected as not needed yet.
