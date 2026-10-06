# 0002. Command line

- Status: accepted
- Date: 2026-10-06
- Capabilities: C23

## Context
C23 asks for one command-line tool usable on Windows, macOS and Linux, where every command says
in one line what it did and the next possible action. Slice 1 only needs to start a ticket.

## Decision
- `argparse` from the standard library, with sub-commands.
- Slice 1 commands:
  - `ariane start <issue-number>`: runs the whole slice 1 flow (ADR 0006) for one issue.
  - `ariane status <issue-number>`: prints the ticket's state, read from its folder.
  - `ariane --version`.
- Every command ends with exactly one summary line on standard output, of the form
  `<what was done>. Next: <next action>.`; details go to the ticket journal.
- Exit codes: 0 success, 1 the ticket stopped (failed check, setup failure, agent error),
  2 usage or configuration error.
- Standard output and error are reconfigured to UTF-8 at start-up, whatever the console code page.

## Consequences
No dependency, predictable help text. Richer interaction (approve, revise) arrives in slice 3 as
new sub-commands.

## Alternatives considered
- `click` or `typer`: nicer help and testing helpers, but a dependency for three commands.
