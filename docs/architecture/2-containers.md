# Level 2: containers

What runs and what is stored.

```mermaid
flowchart TB
  user([Owner or second user])
  cmd[The ariane command]
  repo[(Repository)]
  trees[(Ticket working trees and replay trees in repo.ariane/)]
  folder[(Ticket folder work/n/)]
  verifyrec[(Verify records work/verify/branch/: review.md, checks.md, metrics.json)]
  shadowstore[(Shadow clones repo.ariane/shadow/n/, origin removed)]
  logs[(Log files in repo.ariane/logs/)]
  session["Agent session process: claude, opencode or codex (Codex CLI, an external system, reviewer only)"]
  ci[CI workflows: ci.yml, check-statuses.yml]
  github[GitHub]
  user --> cmd
  cmd -->|creates and removes| trees
  trees -->|worktrees of| repo
  cmd -->|writes brief, journal, checks, review-n, status, metrics.json| folder
  folder -->|lives in the ticket branch of| trees
  cmd -->|starts in a tree| session
  cmd -->|ariane verify commits on the branch| verifyrec
  cmd -->|start --shadow: clones, records metrics.json| shadowstore
  cmd -->|judge: writes verdict and minutes into metrics.json| shadowstore
  cmd -->|report: reads metrics.json| folder
  cmd -->|report: reads metrics.json| verifyrec
  cmd -->|report: reads metrics.json| shadowstore
  cmd -->|report: reads pull request states| github
  cmd -->|technical logs, redacted| logs
  session -->|reviewer: read-only, in a reviewer tree without instruction files| trees
  session -->|edits files in| trees
  cmd -->|push, pull request, statuses| github
  github -->|triggers| ci
  ci -->|publishes statuses from the committed report| github
```

- `ci.yml` runs the checks on Windows, macOS and Linux with Python 3.13, and on Linux with
  Python 3.11 too; the tests run in parallel (ADR 0005, ADR 0047).
- `check-statuses.yml` publishes the statuses from the committed report when Ariane cannot.
- The reviewer session is read-only: its tools are an allow list (`Read`, `Glob`, `Grep`). It reads a
  separate reviewer tree with no `CLAUDE.md`, `AGENTS.md` or `.claude/` (ADR 0031); Claude Code starts
  from an empty folder with `--restricted`. On opencode it ignores project configuration files. On Codex it runs `codex exec` in the read-only sandbox with the CLI's own login; Ariane never reads `~/.codex/auth.json`.
- The shadow clone is separate from the repository and has no remote: a shadow run cannot push (ADR 0036).
- The ticket folder (`brief.md`, `journal.md`, `checks.md`, `review-<n>.md`, `status.md`, `metrics.json`) is committed with the ticket and readable without Ariane.
