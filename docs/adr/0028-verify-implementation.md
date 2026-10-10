# 0028. `ariane verify` implementation choices

- Status: accepted
- Date: 2026-10-10
- Capabilities: C10, C23

## Context
ADR 0016 and ADR 0020 give a branch finished by hand the same verification as a ticket: a clean replay of the checks, one review, the review record. A few details were left open.

## Decision
- The checks run in a detached working tree at the branch's head (`<repo>.ariane/worktrees/verify-<branch>`, `/` becomes `-`), after the setup command, with the same credential-free environment as a ticket's checks. The reviewer runs in that tree, read-only; Ariane checks afterwards that the tree and the branch's head did not move.
- The reviewer is told the issue's text with `--issue` (read through the tracker, which needs the token) and otherwise the branch's commit messages since its merge base with `origin/<base>` (else the local base branch). The diff is taken from that merge base.
- The review runs even when a blocking check fails: the record is complete and the verdict can only be `no-go` through the definition of done.
- The records are `work/verify/<branch>/review.md` and `checks.md` (redacted), committed in one commit on top of the branch's head: in the working tree where the branch is checked out, or else in a temporary one. The journal of the review stays outside the repository. A branch checked out with uncommitted changes is refused, naming them.
- A reviewer that fails (no valid answer twice, stopped session) or a setup that fails commits nothing and exits 1 with the next action.
- The git-configuration snapshot of a ticket's guards is not repeated: the branch is the owner's, not an agent's.

## Consequences
Re-running `verify` after a fix adds a new commit that overwrites the records. Nothing is ever pushed.

## Alternatives considered
- Skip the review when a blocking check fails: rejected, one review is the contract and its findings help the fix.
- Commit with plumbing commands, without a working tree: rejected, more code for the same result.
