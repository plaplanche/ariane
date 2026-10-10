# 0022. Living documentation, generated references and log catalogue

- Status: accepted
- Date: 2026-10-10
- Capabilities: C25, C23; non-functional requirements "Observability" and "Documentation of Ariane"

## Context
The owner wants a newcomer to understand how Ariane works from the repository alone, and the
documentation to stay true as tickets land. Today Ariane has the spec, the ADRs and a README,
but no description of its modules, no reference generated from the code, and no technical log:
only the ticket journal and one line of output. An HTTP API description (OpenAPI) was asked for,
but Ariane is a command-line tool without an HTTP API, so there is nothing for it to describe.

## Decision
- **Architecture documents** in `docs/architecture/`, Markdown with Mermaid diagrams, one per C4
  level: `0-landscape.md` (the people and systems around Ariane: owner, tracker, agent runtimes,
  CI), `1-context.md`, `2-containers.md` (the `ariane` command, the ticket working trees, the
  ticket folder, the CI workflows), `3-components.md` (the modules and how a ticket flows through
  them), and level 4 as `modules/<module>.md`, one per module under `src/ariane/` (role, main
  types and functions, a diagram of its collaborations). Diagrams use Mermaid flowcharts and
  sequence diagrams, which every Markdown viewer that renders Mermaid supports, rather than the
  experimental C4 syntax.
- **Generated references**, committed under `docs/reference/`: `cli.md` from the command-line
  parser, and JSON Schemas of `ariane.toml` and of each agent's structured answer (the
  reviewer's verdict first). One script regenerates them; a test fails when a committed file
  differs from what the script produces, so CI needs no new step. An OpenAPI description is
  generated the day Ariane has an HTTP API, and C25 lets any project declare its own.
- **Logs.** Functional logs are the journal entries of a ticket (C1). Technical logs use the
  standard library's `logging` (no new dependency), at levels debug, info, warning and error;
  the level comes from `--log-level` or `ARIANE_LOG_LEVEL` (default warning); records go to
  standard error and to a log file outside the repository, beside the working trees; every
  record is redacted (C21). Each functional and technical log type is declared once in code
  with a stable identifier, a level and a one-line meaning; `docs/logs.md` is generated from
  those declarations and checked like the other references.
- **Upkeep.** Every ticket updates the documentation its change affects: it is an item of the
  default definition of done (ADR 0023), stated in every issue's acceptance checklist and in
  CLAUDE.md for implementer sessions. A test fails when a module under `src/ariane/` has no
  `docs/architecture/modules/` file or a file names a module that no longer exists. A
  documentation review closes every roadmap slice: by hand in the owner's session until
  `ariane docs-review` (C25, slice 6) runs it.
- **Order** (amends ADR 0020): before the reviewer work of slice 3, tickets create the
  architecture baseline, the generated references and the technical logs with their catalogue.

## Consequences
Every ticket carries a small documentation cost; stale documentation becomes a failing test
for what can be checked mechanically, and a review finding for the rest. The diagrams of level
0 to 3 are written by hand and checked only by review.

## Alternatives considered
- Mermaid's C4 syntax: experimental and not rendered everywhere.
- Documentation generated from docstrings only: covers level 4 but not how the parts fit.
- A third-party documentation or logging library: a dependency for what the standard library
  and a short script do.
- Swagger/OpenAPI now: nothing to describe without an HTTP API.
