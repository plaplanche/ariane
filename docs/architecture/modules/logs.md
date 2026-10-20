# Module `ariane.logs`

Declares every log type once (functional journal entries and technical records) with its identifier, level and meaning, and configures the technical logs: level, standard error, a log file outside the repository, and redaction (C21, C23).

## Public API

| Name | Kind | What it does |
| --- | --- | --- |
| `LOGGER_NAME` | constant | The name of the logger, `ariane`. |
| `LEVEL_VARIABLE` | constant | The variable that sets the level, `ARIANE_LOG_LEVEL`. |
| `DEFAULT_LEVEL` | constant | The level without option or variable: `warning`. |
| `LEVELS` | constant | The level names and their `logging` values. |
| `FUNCTIONAL` | constant | The kind of a journal entry type. |
| `TECHNICAL` | constant | The kind of a technical record type. |
| `LogType` | dataclass | One declared type: `id`, `kind`, `level`, `meaning`. |
| `FUNCTIONAL_TYPES` | constant | The declared journal entry types. |
| `TECHNICAL_TYPES` | constant | The declared technical record types. |
| `functional(type_id)` | function | The declared journal entry type; an undeclared one is refused. |
| `parse_level(name)` | function | The `logging` level of a level name. |
| `resolve_level(option, environ)` | function | The level from `--log-level`, else `ARIANE_LOG_LEVEL`, else warning. |
| `log_path(repo_root, number)` | function | The log file `<repo>.ariane/logs/<n>.log` (`verify-<branch>.log` for `ariane verify`). |
| `add_secrets(secrets)` | function | Register known secrets that every record masks. |
| `configure(level, log_file=None)` | function | Send records of at least `level` to standard error and, if given, to `log_file`. |
| `emit(type_id, message)` | function | Write one technical record naming its declared type. |

## Behaviour and errors

- Writes the log file given to `configure`, beside the working trees and outside the repository; standard error gets the same records. Every record goes through `redact` with the secrets from `add_secrets`.
- `functional` raises `ValueError` for an undeclared type, `emit` a `KeyError`; `parse_level` and `resolve_level` raise `ValueError` for an unknown level name.
- The generated [log catalogue](../../logs.md) lists every declared type.
- Reviewer integrity (C10, ADR 0031) declares, among others: `ticket.review.diff_truncated` (the reviewer's diff was cut; the files to read in the tree), `process.survivors_killed` (processes that outlived a command were killed) and `process.subreaper_failed` (an error: Ariane could not become the subreaper, so `start` and `verify` run nothing).
- Restart (C23, ADR 0047): `ticket.restarted` is the first journal entry of a run started with `ariane start <n> --restart` that cleared something: the trees removed, the kept branch `ariane-restarted/<n>-...` and its head commit, and the previous run's last action read from that branch's `work/<n>/status.md`. A restart with nothing to clear is a plain start and writes none.
- Parallel replay (C9, ADR 0052): `ticket.checks.parallel` is the journal entry of a replay with `project.parallel_checks` above 1: how many checks ran at the same time (fewer than asked when fewer run slots were free) and the run slot each worker held.
- Selective checks (C9, ADR 0056): `ticket.checks.skipped` names the checks a round did not run because no changed file matches their `paths`; `ticket.checks.risk_tier` gives the round's risk tier and its reasons.
- Dependency caches (C9, ADR 0054): `ticket.checks.cache` lists, per check, each `[[project.cache]]` folder copied from the store (hit) or built (stored, or why not); the ticket's own tree's caches and the store entries pruned at the start are in `ticket.setup`.
- Environment (C21): `ticket.env.declared_secret` warns, names only, when variables named like secrets pass to agents and checks because `[project] env` declares them.

## Workflow

```mermaid
flowchart TD
  A[resolve_level option, environ] --> B{--log-level given?}
  B -- yes --> C[parse_level option]
  B -- no --> D{ARIANE_LOG_LEVEL set?}
  D -- yes --> C
  D -- no --> E[default warning]
  C -- unknown name --> X[raise ValueError]
  C --> F[level]
  E --> F
  F --> G[configure level, log_file]
  G --> H[handler on standard error, handler on log_file if given, secrets masked]
  I[emit type_id, message] --> J{type declared?}
  J -- no --> X[raise KeyError]
  J -- yes --> K[write record at the level of its type]
```

## Code view (C4 level 4)

```mermaid
classDiagram
class LogType {
  <<dataclass>>
  id str
  kind str
  level str
  meaning str
}
class logs {
  <<function>>
  functional(type_id) LogType
  parse_level(name) int
  resolve_level(option, environ) int
  log_path(repo_root, number) Path
  add_secrets(secrets) None
  configure(level, log_file) None
  emit(type_id, message) None
  FUNCTIONAL_TYPES tuple~LogType~
  TECHNICAL_TYPES tuple~LogType~
}
logs ..> LogType : declares and returns
logs ..> redact : masks records
```

## Collaborations

Arrows go from the importing module to the imported module; a dashed arrow is an import for type checking only.

<!-- generated: collaborations -->
```mermaid
flowchart LR
  cli --> logs
  flow --> logs
  git --> logs
  github --> logs
  logs --> redact
  process --> logs
  ticket --> logs
```
<!-- end generated -->

## Reference

See the generated [log catalogue](../../logs.md), generated from the declarations (`scripts/generate_docs.py`).

## Serves

C21, C23; ADR 0022, ADR 0047, ADR 0054, ADR 0056. See [the component view](../3-components.md).
