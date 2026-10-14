# 0032. Only run an issue labelled by a maintainer and not edited by anyone else since

- Status: accepted; checks 2 and 3 amended below (#111)
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

## Amendment (2026-10-14, #111): REST only
In a cloud session the proxy answers HTTP 403 to `GET /repos/{repo}/collaborators/{user}/permission`
and to GraphQL ("GitHub GraphQL is not available from Claude Code sessions"), while the issue, its
events and `GET /repos/{repo}` answer 200 (probe of 2026-10-14): the gate above refused every
issue there, including the ticket that would fix it. Checks 2 and 3 become:

2. the user who last added the label is the owner of a user-owned repository (`GET /repos/{repo}`:
   `owner.type` is `User`, logins compared without case), with no permission call; anyone else
   goes through the permissions endpoint as before, and an error other than 404 refuses the
   issue with the user's name and the error;
3. the issue's `updated_at` is not later than that `labeled` event plus 1 second (adding a label
   stamps `updated_at` in the same second, and both carry seconds only). A later change refuses
   the issue: an edit, a rename, a comment or another label, by anyone. GraphQL and the
   `renamed` check are removed.

Stricter than before (a writer's edit or a comment also asks for the label again), and two to
three requests per run (the repository is read once per tracker). Accepted residual risk: REST
shows no event for a body edit, so an edit within the second after the label passes. Ariane's own
activity can also update the issue, for example the cross-reference of a pull request that says
`Closes #N`: a later `ariane start` or `ariane verify --issue N` (a hand takeover) then needs the
label again. A failing `GET /repos/{repo}` is a tracker error (exit 1), not a refusal. An
organisation-owned repository still needs the permissions endpoint.
