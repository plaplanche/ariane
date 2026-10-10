# Level 1: system context

Ariane as one system and what it exchanges with each neighbour.

```mermaid
flowchart LR
  user([Owner or second user])
  ariane[Ariane]
  github[GitHub]
  runtime[Agent runtime: Claude Code]
  vendor[Model vendor]
  user -->|ariane start n| ariane
  ariane -->|one line: what was done, what next| user
  ariane -->|read an issue| github
  ariane -->|push one branch| github
  ariane -->|open a pull request| github
  ariane -->|publish statuses| github
  ariane -->|start agent sessions, prompt and trimmed environment| runtime
  runtime -->|structured result| ariane
  runtime -->|model calls| vendor
```

Only Ariane pushes, and only once, after the checks passed on a clean replay (ADR 0018).
Agents never receive the GitHub token.
