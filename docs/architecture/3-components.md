# Level 3: components

## Modules and their dependencies

An arrow goes from a module to a module it imports. Each module has a file in
[`modules/`](modules/).

```mermaid
flowchart TD
  __main__ --> cli
  checks --> process
  checks --> config
  checks --> ticket
  claude_code --> process
  claude_code --> runtime
  opencode --> process
  opencode --> runtime
  cli --> config
  config --> config_schema
  cli --> flow
  cli --> verify
  cli --> git
  cli --> process
  cli --> ticket
  cli --> claude_code
  cli --> opencode
  cli --> runtime
  cli --> github
  context --> git
  context --> config
  context --> tracker
  delivery --> checks
  delivery --> review
  delivery --> git
  delivery --> process
  delivery --> ticket
  delivery --> redact
  delivery --> tracker
  flow --> checks
  flow --> context
  flow --> git
  flow --> process
  flow --> ticket
  flow --> config
  flow --> delivery
  flow --> redact
  flow --> review
  flow --> review_session
  flow --> runtime
  flow --> tracker
  git --> process
  review_session --> checks
  review_session --> config
  review_session --> review
  review_session --> runtime
  review_session --> ticket
  review_session --> tracker
  review --> checks
  review --> config
  review --> context
  review --> tracker
  git --> process
  git --> redact
  github --> tracker
  logs --> redact
  cli --> logs
  flow --> logs
  git --> logs
  github --> logs
  process --> logs
  ticket --> logs
  ticket --> redact
  ticket --> tracker
  verify --> checks
  verify --> context
  verify --> flow
  verify --> git
  verify --> process
  verify --> review
  verify --> review_session
  verify --> ticket
  verify --> config
  verify --> redact
  verify --> runtime
  verify --> tracker
```

## `ariane start <n>`

```mermaid
sequenceDiagram
  actor U as User
  participant CLI as cli
  participant F as flow
  participant T as tracker (github)
  participant G as git
  participant R as runtime (claude_code or opencode)
  participant C as checks
  participant D as delivery
  U->>CLI: ariane start n
  CLI->>F: start
  F->>T: read the issue
  F->>G: add the ticket working tree
  F->>F: setup command, ticket folder brief
  F->>R: run the implementer session
  R-->>F: SessionResult
  F->>G: guard checks (configuration, branch, untracked files)
  F->>G: commit
  F->>G: add a clean replay tree
  F->>C: replay the checks
  C-->>F: results
  F->>R: run a read-only reviewer session in the replay tree
  R-->>F: answer (validated by review, one retry)
  F->>G: verify git, the tree and the remote did not change
  F->>F: review-0.md; go continues
  loop at most two fix rounds, while the review is no-go
    F->>R: run a fresh implementer session with the findings
    F->>G: guard checks, commit, clean replay, checks
    F->>R: run a read-only reviewer session (review-1.md, review-2.md)
  end
  F->>D: deliver
  D->>G: one push
  D->>T: open the pull request (a draft, needs a human, if still no-go)
  D->>T: publish statuses
  F-->>CLI: Outcome
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
  participant R as runtime (claude_code or opencode)
  U->>CLI: ariane verify branch
  CLI->>V: verify
  V->>G: refuse a checked-out branch with uncommitted changes
  V->>G: add a clean replay tree at the branch head
  V->>V: setup command
  V->>C: replay the checks
  C-->>V: results
  V->>R: run a read-only reviewer session in the replay tree
  R-->>V: answer (validated by review, one retry)
  V->>G: commit work/verify/branch/review.md and checks.md on the branch
  V-->>CLI: Outcome
  CLI-->>U: one line (never pushes)
```
