# Module `ariane.cli`

The `ariane` command line (C23). It parses arguments, wires the configuration, tracker and runtime, calls the flow, and ends every command with one line saying what it did and what comes next.

## Public API

| Name | Kind | What it does |
| --- | --- | --- |
| `EXIT_OK` | constant | Exit code 0, re-exported from `flow`. |
| `EXIT_STOPPED` | constant | Exit code of a stopped ticket, re-exported from `flow`. |
| `EXIT_USAGE` | constant | Exit code 2: a usage or configuration problem. |
| `main(argv=None)` | function | The entry point: parse `argv`, run the command, return the exit code. |

## Behaviour and errors

- Commands: `start [--shadow] [--restart | --resume]` (`--shadow`: the ticket runs in a separate clone through `shadow`, C19, ADR 0036; `--restart`: a stopped or interrupted ticket starts over through `flow.start(restarting=True)`, its trees removed and its branch kept, ADR 0047; `--resume`: a ticket stopped by its implementer's limit or a quota continues from its saved work through `flow.start(resuming=True)`, ADR 0062, and cannot be given with `--restart`; `--shadow` with either exits 2 before the configuration is read: "--restart (or --resume) does not apply to shadow tickets", next action: remove the clone), `status`, `judge <n> accept|reject --minutes N [--note TEXT]` (records the human's verdict and time on a shadow ticket through `shadow.judge`, C19, ADR 0037), `report [--since YYYY-MM-DD]` (from `report`, C19, ADR 0038), `update <n>` (merges the base branch into a delivered ticket's branch, replays, reviews and pushes on go through `update.update`, C11, ADR 0033; it reads the issue through the issue gate like `start`, and its log file is `update-<n>.log`), `verify <branch> [--issue N]` (checks and reviews a local branch finished by hand, C23, ADR 0028) and `next [--start]` (proposes the next issue of the queue that can start next to the running tickets through `next_start.show`, printing each issue's reasons then the `Next:` line, exit 1 when nothing is proposed; `--start` starts the proposal last printed through `next_start.start`, launching `next_start.spawn` with the token in the child's environment, ADR 0060; its log file is `next.log`; a tracker, git or file error exits 1 naming it).
- Reads `ariane.toml` (or the file `ARIANE_CONFIG` names) through `config.load`, the token variable the configuration names, `ARIANE_LOG_LEVEL`; writes the log file `<repo>.ariane/logs/<name>.log` through `logs`.
- Token scope (C21, ADR 0017): once read, the token variable is removed from `os.environ` (`_take_token`); the run gets a copy of the environment that carries it, and the process is made undumpable on Linux (`process.make_undumpable`). It also becomes the subreaper of its orphaned descendants on Linux (`process.set_child_subreaper`), so a process an agent starts in a new session can be found and killed; if Linux refuses, `start`, `update` and `verify` do nothing and say why (C10, ADR 0031).
- `start`, `update`, `next` and `verify --issue` build the `GitHubTracker` with `[tracker].ready_label`, so both apply the issue gate (C21, ADR 0032). `report` builds it only when the configuration and the token exist (else waiting time is "not available"), and reads `[checks_policy] max_escape_rate` from the configuration (0.02 without it).
- The runtime of each role comes from `[agents.<role>].runtime` (`RoutedRuntime`, ADR 0029).
- Exit codes: `EXIT_OK` when the command did what was asked, `EXIT_STOPPED` for a ticket that stopped, `EXIT_USAGE` (2) for an invalid configuration, an empty token variable, a bad argument or a directory outside a git repository; each prints its reason and `Next:` step.
- `status` reads `work/<n>/status.md` from the ticket's working tree or the repository, else from the base branch on the remote (merged ticket).

## Workflow

```mermaid
flowchart TD
  A[main argv] --> B[parse arguments, set UTF-8 console]
  B --> C{usage error?}
  C -- yes --> X[exit 2]
  C -- no --> D[find repository root]
  D --> E{inside a git repository?}
  E -- no --> U[say Did nothing, return EXIT_USAGE]
  E -- yes --> F{command}
  F -- report --> R[report.build, print lines]
  F -- judge --> J[shadow.judge]
  F -- verify --> V[config.load, tracker if --issue, verify.verify]
  F -- update --> W[config.load, check token, build tracker and runtime, update.update]
  F -- status --> S[read status.md, else remote base branch]
  F -- next --> N[config.load, check token, build tracker; next_start.show, or next_start.start with --start]
  N --> Z
  F -- start --> T[config.load, check token, build tracker and runtime]
  F -- "start --shadow --restart" --> X2[say Did not start, return EXIT_USAGE]
  T --> G{shadow?}
  G -- yes --> H[shadow.start]
  G -- no --> I[flow.start, restarting with --restart, resuming with --resume]
  V --> Z
  R --> Z
  J --> Z
  S --> Z
  H --> Z
  I --> Z
  Z[print one line, return exit code]
  T -- ConfigError or empty token --> U
```

## Code view (C4 level 4)

```mermaid
classDiagram
class cli {
  <<function>>
  main(argv) int
  EXIT_OK
  EXIT_STOPPED
  EXIT_USAGE
}
class flow
class shadow
class verify
class update
class report
class next_start
class config
class GitHubTracker
cli ..> flow : start, Outcome
cli ..> shadow : start, judge
cli ..> verify : verify
cli ..> update : update
cli ..> report : build
cli ..> next_start : show, start, spawn
cli ..> config : load, Config
cli ..> GitHubTracker : builds
```

## Collaborations

Arrows go from the importing module to the imported module; a dashed arrow is an import for type checking only.

<!-- generated: collaborations -->
```mermaid
flowchart LR
  __main__ --> cli
  cli --> claude_code
  cli --> codex
  cli --> config
  cli --> flow
  cli --> git
  cli --> github
  cli --> logs
  cli --> next_start
  cli --> opencode
  cli --> pi
  cli --> process
  cli --> report
  cli --> risk
  cli --> runtime
  cli --> shadow
  cli --> ticket
  cli --> tracker
  cli --> update
  cli --> verify
```
<!-- end generated -->

## Reference

See the generated [command-line reference](../../reference/cli.md), generated from the code (`scripts/generate_docs.py`).

## Serves

C23; ADR 0002, ADR 0047. See [the component view](../3-components.md).
