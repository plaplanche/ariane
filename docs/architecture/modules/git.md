# Module `ariane.git`

The git operations Ariane performs itself: working trees, snapshots of the git configuration, guards against edits outside the tree, commits and the single authenticated push.

## Main types and functions

- `git`, `out`: run git and return output.
- `add_worktree`, `add_detached_worktree`, `remove_worktree`: ticket and replay trees.
- `config_snapshot`, `snapshot_changes`: detect configuration tampering.
- `blocked_push_env`, `push_env`, `push`: push only from Ariane.
- `commit`, `head`, `changed_paths`, `committed_paths`, `is_ancestor`, `fast_forwarded`: history queries.
- `GitError`: raised on a failing git command.

## Collaborations

Arrows go from the caller to the callee.

```mermaid
flowchart LR
  git --> process
  git --> logs
  git --> redact
  cli --> git
  context --> git
  delivery --> git
  flow --> git
```

## Serves

C8, C11, C21; ADR 0017, ADR 0018. See [the component view](../3-components.md).
