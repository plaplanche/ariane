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
  checks --> ticket
  claude_code --> attempts
  claude_code --> process
  claude_code --> runtime
  cli --> claude_code
  cli --> config
  cli --> flow
  cli --> git
  cli --> github
  cli --> logs
  cli --> opencode
  cli --> process
  cli --> report
  cli --> runtime
  cli --> shadow
  cli --> ticket
  cli --> verify
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
  flow --> review
  flow --> runtime
  flow --> stop
  flow --> ticket
  flow --> tracker
  git --> logs
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
  process --> logs
  replay --> checks
  replay --> delivery
  replay -.-> flow
  replay --> git
  replay --> review
  replay --> review_session
  replay --> stop
  replay --> ticket
  report --> measures
  report --> metrics
  report --> shadow
  report --> ticket
  report --> tracker
  review --> checks
  review --> config
  review --> context
  review --> tracker
  review_session --> checks
  review_session --> config
  review_session --> metrics
  review_session --> review
  review_session --> runtime
  review_session --> ticket
  review_session --> tracker
  runtime --> attempts
  shadow --> checks
  shadow --> config
  shadow --> flow
  shadow --> git
  shadow --> metrics
  shadow --> review
  shadow --> runtime
  shadow --> stop
  shadow --> ticket
  shadow --> tracker
  ticket --> logs
  ticket --> redact
  ticket --> tracker
  verify --> checks
  verify --> config
  verify --> context
  verify --> flow
  verify --> git
  verify --> metrics
  verify --> process
  verify --> redact
  verify --> review
  verify --> review_session
  verify --> runtime
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
  participant G as git
  participant R as runtime (claude_code or opencode)
  participant P as replay
  participant C as checks
  participant S as review_session
  participant M as metrics
  participant D as delivery
  U->>CLI: ariane start n
  CLI->>F: start
  F->>T: read the issue
  F->>G: add the ticket working tree
  F->>F: setup command, ticket folder brief
  F->>R: run the implementer session
  R-->>F: SessionResult
  F->>M: write metrics.json
  F->>G: guard checks (configuration, branch, untracked files)
  F->>G: commit
  F->>P: replay and review
  P->>G: add a clean replay tree
  P->>C: replay the checks
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
  participant R as runtime (claude_code or opencode)
  participant C as checks
  participant V as review
  participant M as metrics
  U->>CLI: ariane start --shadow n
  CLI->>H: run_shadow
  H->>T: read the issue (the only call to the tracker)
  H->>G: clone into repo.ariane/shadow/n, remove the origin
  H->>R: run the implementer session in the clone
  R-->>H: SessionResult
  H->>M: write metrics.json in the clone
  H->>G: commit in the clone
  H->>C: replay the checks
  C-->>H: results
  H->>R: run a read-only reviewer session
  R-->>H: answer
  H->>V: validate the answer
  H->>M: write metrics.json in the clone
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
  participant R as runtime (claude_code or opencode)
  participant M as metrics
  U->>CLI: ariane verify branch
  CLI->>V: verify
  V->>G: refuse a checked-out branch with uncommitted changes
  V->>G: add a clean replay tree at the branch head
  V->>V: setup command
  V->>C: replay the checks
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
  U->>CLI: ariane report --since
  CLI->>P: report
  P->>M: read work/*/metrics.json and work/verify/**/metrics.json
  P->>H: read the metrics of the shadow clones
  P->>T: read pull request states (human time)
  P->>E: lines and totals
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
