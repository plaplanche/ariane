# 0032. Only run an issue labelled by a maintainer and not edited by anyone else since

- Status: accepted
- Date: 2026-10-13
- Capabilities: C21, C22, C1

## Context
The repository is public: anyone can open or edit an issue, and its title and body become the
implementer's task, run with `bypassPermissions` and a shell. The untrusted-data tags are not a
boundary. An outside analysis of 2026-10-11 rates the prompt injection by the issue as high.

## Decision
`[tracker]` gains `ready_label` (string, default `"ariane"`). Before reading the task, in
`GitHubTracker.read_issue` (so for `ariane start` and `ariane verify --issue`), Ariane checks:

1. the issue carries `ready_label`;
2. the last `labeled` event for that label was made by a user whose permission on the repository
   is `write`, `maintain` or `admin` (`GET /repos/{repo}/collaborators/{user}/permission`);
3. since that moment, no user without that permission changed the title (`renamed` events) or the
   body (GraphQL `lastEditedAt` and `editor`). An edit at the very second of the label counts as
   after it.

A failing check raises `IssueRefused`, naming the reason and how to fix it; the command exits 2
before any branch, worktree or agent. A missing actor or editor (deleted account) has no
permission. The GraphQL endpoint is `<api_url>/graphql`, or `/api/graphql` on a GitHub Enterprise
Server `/api/v3` address.

## Consequences
A maintainer must label each ticket to run, and add the label again after any later edit by
someone else. Only the last body edit is visible: a reader's edit followed by a writer's edit is
accepted, the writer being responsible for what they saved. Comments are never read by agents.
The check costs three to four requests per run.

## Alternatives considered
- An allow list of issue authors: it ignores edits by others and needs upkeep in `ariane.toml`.
- No check: leaves the prompt injection open.
