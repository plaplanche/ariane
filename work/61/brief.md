# Product brief: Add technical logs by level and a generated catalogue of log types (ADR 0022)

- Source: issue #61 (https://github.com/plaplanche/ariane/issues/61)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

Spec, non-functional requirement "Observability", and ADR 0022: technical logs at levels debug, info, warning and error, chosen by `--log-level` or `ARIANE_LOG_LEVEL` (default warning), written to standard error and to a log file outside the repository, redacted (C21); every functional log type (journal entry) and technical log type has a stable identifier, and `docs/logs.md`, generated from the code, lists them with their level and meaning.

## Current state

- Functional logs: `TicketFolder.log(title, body)` in `src/ariane/ticket.py`, called with free titles from `src/ariane/flow.py` (about 11 calls: "Setup", "Implementer session started", "Verified after …", "Agent work committed", "Stopped: …") and `src/ariane/delivery.py` (4 calls: "Delivering", "Pushed", "Delivered", "Warning: commit statuses refused").
- No technical log: no `logging` use; `cli.py` prints one line per command.

## Decided spec

- `src/ariane/logs.py` declares every log type once: identifier (for example `ticket.session.started`), kind (functional or technical), level, a one-line meaning. `TicketFolder.log` takes a declared functional type (its title stays human-readable, with details after it); a journal entry with an undeclared type is impossible.
- Technical logs use the standard library's `logging` under the logger `ariane`, with records naming their declared type. At least: each git command run (debug), each subprocess started and its exit and duration (debug), each GitHub API call and its status (info), each guard verification (info), each warning already journaled (warning), each stop (error).
- `--log-level` (on every command) and `ARIANE_LOG_LEVEL` set the level, the option winning; an invalid level is refused with a one-line message. Records go to standard error and to `<repo>.ariane/logs/<n>.log` (appended, created as needed). A filter redacts every record with `redact.redact` and the known secrets.
- The docs generator (`scripts/generate_docs.py`, from the generated-references issue) writes `docs/logs.md`: two tables, functional and technical, with identifier, level and meaning; its `--check` covers it.
- `docs/architecture/` gains `modules/logs.md` and the changed modules' files are updated.

## Release note

Added: technical logs by level (`--log-level`, `ARIANE_LOG_LEVEL`) and a catalogue of every log type.

## Acceptance criteria

- Tests named `test_obs_logs_*` show: debug records appear at debug and not at warning; the option wins over the variable; an invalid level is refused; a token in a log message is masked in standard error and in the file; the log file is outside the repository; every `TicketFolder.log` call uses a declared type; `docs/logs.md` matches the declarations.
- All checks in CLAUDE.md pass.

## Acceptance checklist

- [ ] `uv run pytest -k obs_logs` runs at least 6 tests and they pass.
- [ ] Definition of done: `docs/logs.md` regenerated; `docs/architecture/modules/logs.md` added and the files of changed modules updated.
- [ ] All checks in CLAUDE.md pass.

## Out of scope

Log rotation, structured (JSON) log output, posting logs anywhere.

## Related

ADR 0022, spec "Observability", C21.
