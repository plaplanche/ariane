# 0006. Slice 1 ticket flow: folder, working tree, delivery

- Status: accepted
- Date: 2026-10-06
- Capabilities: C1, C8, C9, C11, C23

## Context
Slice 1's gate: a real issue becomes a pull request whose checks Ariane replayed green. Stages
and approvals (C2) arrive in slice 3, so `ariane start` runs the flow straight through.

## Decision
`ariane start <n>` does, in order, writing each step to the journal:

1. Load and validate `ariane.toml` (ADR 0003).
2. Read issue `n` (title and body only, never comments) through the tracker interface. A number
   that is a pull request is refused.
3. Fetch `origin/<base_branch>`. Refuse, before any agent runs, when the ticket's working tree,
   a local branch `ariane/<n>` or a remote branch `ariane/<n>` already exists (resume is slice 5).
4. Create branch `ariane/<n>` from `origin/<base_branch>` in a new git working tree outside the
   main checkout, at `<repo-parent>/<repo-name>.ariane/worktrees/<n>`.
5. Run the setup command, if any (C8): a failure stops the ticket with its output; files left
   that git does not ignore stop the ticket with a message asking to ignore them.
6. Create the ticket folder `work/<n>/`: `brief.md` prefilled from the issue (status `draft`) and
   `journal.md`. It is created after setup so that it is not mistaken for a setup leftover.
7. Run one implementer session (ADR 0007) with a context Ariane assembles itself.
8. Verify the agent did not switch branch, rewrite history, change git configuration, hooks or
   local branches, or change any branch or tag on the remote (ADR 0007). Refuse when it changed
   no file outside `work/`. Commit what it left outside `work/`, as Ariane.
9. Run every declared check, all of them even when one fails (C9), in the same credential-free
   environment as the agent: checks run code the agent wrote. Verify again, and also that the
   branch still points at the commit that was checked. The full report goes to
   `work/<n>/checks.md`, one section per check with its complete output and a summary line.
10. Commit the ticket folder, rewritten exactly as Ariane recorded it.
11. If a blocking check failed: stop, exit code 1, no push.
12. Otherwise push exactly the checked commit plus Ariane's record commit, with an explicit
    remote URL, and open a pull request against the base branch. Its body holds the summary
    table, a link to `work/<n>/checks.md` on the ticket branch (readable only by people with
    access to the repository) and `Closes #<n>`. If the pull request is refused after the push,
    the ticket stops and says how to finish by hand. The human merges.

The setup command runs with Ariane's environment: it runs before any agent, on the base
branch's code. Ariane's own git commands never run hooks (ADR 0007), so in slice 1 a project's
commit hooks do not run on the commits Ariane makes.

The main checkout is never modified, and Ariane never pushes to the base branch. The ticket
folder is committed on the ticket branch, so the pull request carries it.

## Consequences
The whole state of a ticket is readable by opening `work/<n>/` (C23), including complete check
output. The pull request body stays short, well under GitHub's size limit. Baseline checks on the
base branch (C9) are deferred to slice 4, with the rest of C9's complete form.

## Alternatives considered
- Working trees inside the repository (`.ariane/`, git-ignored): simpler paths, but tools that
  scan the repository (test collectors, editors) may walk into them.
- Truncating check output in the report: keeps files small but hides the failure the human needs.
- Posting the full output as tracker comments: noisy, and split across comments past 65,536
  characters.
- Asking the agent to commit and push: contradicts C11 (agents never push).
