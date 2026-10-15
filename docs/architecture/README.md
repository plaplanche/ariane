# Architecture of Ariane

How Ariane works, in Mermaid diagrams (flowcharts and sequence diagrams, ADR 0022), one file per
C4 level. Each level zooms into the previous one.

| Level | File | Shows |
| --- | --- | --- |
| 0 | [`0-landscape.md`](0-landscape.md) | The people and systems around Ariane. |
| 1 | [`1-context.md`](1-context.md) | Ariane as one system and what it exchanges with each neighbour. |
| 2 | [`2-containers.md`](2-containers.md) | The command, the working trees, the ticket folder, the sessions, the CI workflows. |
| 3 | [`3-components.md`](3-components.md) | The modules, their dependencies, and `ariane start <n>` and `ariane verify <branch>` step by step. |
| 4 | [`modules/`](modules/) | One file per module under `src/ariane/`. |

A test (`tests/test_docs_architecture.py`) fails when a module has no file in `modules/` or a file
there names a module that does not exist. Update these files in the same ticket as the code
(CLAUDE.md rule 11).

Some parts are generated from the code (ADR 0039), between `<!-- generated: <name> -->` and
`<!-- end generated -->`: the dependency graph of `3-components.md` (`dependencies`), the
"Collaborations" diagram of each module file (`collaborations`) and the module list below
(`modules`). Do not edit them by hand: run `uv run python scripts/generate_docs.py` to regenerate
them, `--check` (run by `tests/test_docs_reference.py`) fails when one differs. The text outside
the markers is hand-written.

```mermaid
flowchart LR
  L0[0 landscape] --> L1[1 context] --> L2[2 containers] --> L3[3 components] --> L4[4 modules]
```

## Modules

<!-- generated: modules -->
- [`__main__`](modules/__main__.md)
- [`attempts`](modules/attempts.md)
- [`checks`](modules/checks.md)
- [`claude_code`](modules/claude_code.md)
- [`cli`](modules/cli.md)
- [`config`](modules/config.md)
- [`config_schema`](modules/config_schema.md)
- [`context`](modules/context.md)
- [`delivery`](modules/delivery.md)
- [`flow`](modules/flow.md)
- [`git`](modules/git.md)
- [`github`](modules/github.md)
- [`logs`](modules/logs.md)
- [`measures`](modules/measures.md)
- [`metrics`](modules/metrics.md)
- [`opencode`](modules/opencode.md)
- [`process`](modules/process.md)
- [`redact`](modules/redact.md)
- [`replay`](modules/replay.md)
- [`report`](modules/report.md)
- [`review`](modules/review.md)
- [`review_session`](modules/review_session.md)
- [`runtime`](modules/runtime.md)
- [`shadow`](modules/shadow.md)
- [`stop`](modules/stop.md)
- [`ticket`](modules/ticket.md)
- [`tracker`](modules/tracker.md)
- [`verify`](modules/verify.md)
<!-- end generated -->
