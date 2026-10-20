# Level 3: components

## Modules and their dependencies

An arrow goes from the importing module to the imported module; a dashed arrow is an import for
type checking only. Each module has a file in
[`modules/`](modules/).

<!-- generated: dependencies -->
```mermaid
flowchart TD
  __main__ --> cli
  checks --> config
  checks --> process
  checks --> stop
  checks --> ticket
  claude_code --> attempts
  claude_code --> process
  claude_code --> runtime
  cli --> claude_code
  cli --> codex
  cli --> config
  cli --> flow
  cli --> git
  cli --> github
  cli --> logs
  cli --> opencode
  cli --> pi
  cli --> process
  cli --> report
  cli --> runtime
  cli --> shadow
  cli --> ticket
  cli --> verify
  codex --> process
  codex --> runtime
  config --> cache
  config --> config_schema
  context --> config
  context --> git
  context --> tracker
  delivery --> checks
  delivery --> git
  delivery --> process
  delivery --> redact
  delivery --> review
  delivery --> ticket
  delivery --> tracker
  flow --> checks
  flow --> config
  flow --> context
  flow --> delivery
  flow --> git
  flow --> logs
  flow --> metrics
  flow --> process
  flow --> redact
  flow --> replay
  flow --> restart
  flow --> review
  flow --> review_session
  flow --> runs
  flow --> runtime
  flow --> slots
  flow --> stop
  flow --> ticket
  flow --> tracker
  git --> logs
  git --> pi
  git --> process
  git --> redact
  github --> logs
  github --> tracker
  logs --> redact
  measures --> tracker
  metrics --> attempts
  metrics --> runtime
  metrics --> ticket
  opencode --> attempts
  opencode --> process
  opencode --> runtime
  pi --> config_schema
  pi --> process
  pi --> runtime
  process --> logs
  replay --> cache
  replay --> checks
  replay --> config
  replay --> context
  replay --> delivery
  replay -.-> flow
  replay --> git
  replay --> process
  replay --> restart
  replay --> review
  replay --> review_session
  replay --> slots
  replay --> stop
  replay --> ticket
  report --> measures
  report --> metrics
  report --> shadow
  report --> ticket
  report --> tracker
  restart --> git
  restart --> metrics
  restart --> slots
  restart --> stop
  restart --> ticket
  review --> checks
  review --> config
  review --> context
  review --> ticket
  review --> tracker
  review_session --> checks
  review_session --> config
  review_session --> git
  review_session --> metrics
  review_session --> review
  review_session --> runtime
  review_session --> ticket
  review_session --> tracker
  runs --> git
  runs --> process
  runs --> restart
  runs --> stop
  runtime --> attempts
  runtime --> config
  shadow --> checks
  shadow --> config
  shadow --> flow
  shadow --> git
  shadow --> metrics
  shadow --> review
  shadow --> runtime
  shadow --> slots
  shadow --> stop
  shadow --> ticket
  shadow --> tracker
  slots --> stop
  ticket --> logs
  ticket --> redact
  ticket --> tracker
  verify --> cache
  verify --> checks
  verify --> config
  verify --> context
  verify --> flow
  verify --> git
  verify --> metrics
  verify --> process
  verify --> redact
  verify --> replay
  verify --> review
  verify --> review_session
  verify --> runtime
  verify --> slots
  verify --> stop
  verify --> ticket
  verify --> tracker
```
<!-- end generated -->

## `ariane start <n>`

```mermaid
sequenceDiagram
  actor U as User
  participant CLI as cli
  participant F as flow
  participant T as tracker (github)
  participant L as restart
  participant N as runs
  participant G as git
  participant R as runtime (claude_code, opencode or codex)
  participant P as replay
  participant C as checks
  participant S as review_session
  participant M as metrics
  participant D as delivery
  U->>CLI: ariane start n [--restart]
  CLI->>F: start
  F->>T: read the issue
  F->>L: hold repo.ariane/locks/n.lock until the end (refused if another process holds it)
  F->>N: register the run in repo.ariane/runs/n, with --restart the kept branch name (refused if a live run has it)
  F->>L: prepare
  L->>G: fetch; refuse if ariane/n is on the remote
  opt --restart
    L->>G: save the uncommitted work of tree n in a commit (temporary index)
    L->>G: remove the trees n, n-review, n-replay* (unknown folders as folders); rename ariane/n to ariane-restarted/n-time, the saved commit on top
  end
  L->>G: refuse leftovers (next: --restart), add the ticket working tree
  F->>F: journal ticket.restarted first when it started over
  F->>F: setup command, ticket folder brief
  F->>R: run the implementer session
  R-->>F: SessionResult
  F->>M: write metrics.json
  F->>G: guard checks (configuration, branch, untracked files)
  F->>N: snapshot git first, then drop the changes that are another registered run's own branch and keys
  F->>G: commit
  F->>P: replay and review
  P->>G: the round's diff from the start commit (one read, for the selection and the review)
  Note over P: only the checks the changed files select run; the others are skipped (ADR 0056)
  Note over P: parallel_checks above 1: up to that many workers, each with its own slot (ADR 0052)
  loop for each selected check, in declared order, up to parallel_checks at the same time
    P->>G: add a clean replay tree (setup runs there, with the worker's ARIANE_SLOT)
    P->>C: run that check, with ARIANE_CHANGED_FILES
    P->>G: verify git, the trees and the remote, remove the tree
  end
  Note over P: a stop in one worker or Ctrl-C kills the others' commands; every tree is removed
  C-->>P: results
  alt a blocking check failed
    P-->>F: stop before any review, push nothing
  end
  P->>S: review in the reviewer tree (no instruction files, ADR 0031)
  S->>R: run a read-only reviewer session
  R-->>S: answer (validated by review, one retry)
  S-->>P: review-0.md; go continues
  P->>G: verify git, the tree and the remote did not change
  loop at most two fix rounds, while the review is no-go
    F->>R: run a fresh implementer session with the findings
    F->>M: write metrics.json
    F->>G: guard checks, commit
    F->>P: clean replay, checks, review (review-1.md, review-2.md)
  end
  F->>D: deliver
  D->>G: one push
  D->>T: open the pull request (a draft, needs a human, if still no-go)
  D->>T: publish statuses
  D->>G: commit the record of the pull request (local branch only, not pushed)
  F->>N: append the run to ended.jsonl, then remove its entry (however the run ends)
  F-->>CLI: Outcome
  CLI-->>U: one line
```

## `ariane start --shadow <n>`

The run reads the issue only: no push, no pull request, no status, nothing written to the tracker
(ADR 0036). Everything is recorded in a separate clone with its origin removed.

```mermaid
sequenceDiagram
  actor U as User
  participant CLI as cli
  participant H as shadow
  participant T as tracker (github)
  participant G as git
  participant F as flow
  participant R as runtime (claude_code, opencode or codex)
  participant M as metrics
  participant P as replay
  participant S as review_session
  U->>CLI: ariane start --shadow n
  CLI->>H: start
  H->>T: read the issue (the only call to the tracker)
  H->>G: clone into repo.ariane/shadow/n, remove the origin
  H->>F: run the ticket in the clone (ShadowRun, a flow run)
  F->>R: run the implementer session
  R-->>F: SessionResult
  F->>M: write metrics.json in the clone
  F->>G: guard checks, commit in the clone
  F->>P: replay and review
  P->>S: review in the reviewer tree
  S->>R: run a read-only reviewer session
  R-->>S: answer
  S-->>P: review result
  F->>M: write metrics.json in the clone
  loop up to two fix rounds
    F->>R: run the implementer again on the findings
    F->>P: replay and review
    F->>M: write metrics.json in the clone
  end
  Note over F,H: delivery is replaced by the local record (ShadowRun overrides it)
  H-->>CLI: Outcome (stop before push, pull request and statuses)
  CLI-->>U: one line
```

## `ariane verify <branch>`

```mermaid
sequenceDiagram
  actor U as User
  participant CLI as cli
  participant V as verify
  participant G as git
  participant C as checks
  participant S as review_session
  participant R as runtime (claude_code, opencode or codex)
  participant M as metrics
  U->>CLI: ariane verify branch
  CLI->>V: verify
  V->>G: refuse a checked-out branch with uncommitted changes
  loop for each check, up to parallel_checks at the same time, each worker with its own slot
    V->>G: add a clean replay tree at the branch head
    V->>V: setup command
    V->>C: run that check
    V->>G: remove the tree
  end
  C-->>V: results
  V->>S: review in the `-reviewer` tree (no instruction files, ADR 0031)
  S->>R: run a read-only reviewer session
  R-->>S: answer (validated by review, one retry)
  S-->>V: review result
  V->>M: write metrics.json
  V->>G: commit work/verify/branch/review.md, checks.md and metrics.json on the branch
  V-->>CLI: Outcome
  CLI-->>U: one line (never pushes)
```

## `ariane report [--since]`

```mermaid
sequenceDiagram
  actor U as User
  participant CLI as cli
  participant P as report
  participant M as metrics
  participant H as shadow
  participant T as tracker (github)
  participant E as measures
  U->>CLI: ariane report [--since]
  CLI->>P: report
  P->>M: take the metrics.json name (report reads and validates work/*/metrics.json and work/verify/**/metrics.json itself)
  P->>H: take the shadow clone paths (report reads their metrics.json itself)
  P->>E: lines and totals
  E->>T: read pull request states (human time)
  E-->>P: measures
  P-->>CLI: the report
  CLI-->>U: the table
```

## `ariane judge`

```mermaid
sequenceDiagram
  actor U as User
  participant CLI as cli
  participant H as shadow
  U->>CLI: ariane judge n accept|reject --minutes N
  CLI->>H: judge
  H->>H: write the verdict and the minutes into the shadow metrics.json
  H-->>CLI: Outcome
  CLI-->>U: one line
```
