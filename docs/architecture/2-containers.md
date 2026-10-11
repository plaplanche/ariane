# Level 2: containers

What runs and what is stored.

```mermaid
flowchart TB
  user([Owner or second user])
  cmd[The ariane command]
  repo[(Repository)]
  trees[(Ticket working trees and replay trees in repo.ariane/)]
  folder[(Ticket folder work/n/)]
  verifyrec[(Verify records work/verify/branch/)]
  logs[(Log files in repo.ariane/logs/)]
  session[Agent session process: claude or opencode]
  ci[CI workflows: ci.yml, check-statuses.yml]
  github[GitHub]
  user --> cmd
  cmd -->|creates and removes| trees
  trees -->|worktrees of| repo
  cmd -->|writes brief, journal, report, status| folder
  folder -->|lives in the ticket branch of| trees
  cmd -->|starts in a tree| session
  cmd -->|ariane verify commits on the branch| verifyrec
  cmd -->|technical logs, redacted| logs
  session -->|reviewer: read-only, in a replay tree| trees
  session -->|edits files in| trees
  cmd -->|push, pull request, statuses| github
  github -->|triggers| ci
  ci -->|publishes statuses from the committed report| github
```

- `ci.yml` runs the checks on Windows, macOS and Linux (ADR 0005).
- `check-statuses.yml` publishes the statuses from the committed report when Ariane cannot.
- The reviewer session is read-only: its tools exclude writing and it runs in a clean replay tree.
  On opencode it ignores project configuration files.
- The ticket folder is committed with the ticket and readable without Ariane.
