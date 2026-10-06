# Product brief: Publish each check's result as a commit status on the pull request (C9)

- Status: draft
- Approved: not yet
- Source: issue #5 (https://github.com/plaplanche/ariane/issues/5)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

C9 (`docs/spec.md`): "Ariane publishes each check's result as a status on the pull request's head commit (a GitHub commit status; the equivalent on other trackers), so the results show next to the pull request and branch protection can require them." It is scheduled in slice 2 of the roadmap. It uses a commit status, not a check run, because check runs need a GitHub App and Ariane uses a personal token (ADR 0007).

## Current state

- `src/ariane/flow.py`, `_TicketRun._check_and_deliver`: runs the checks, writes `work/<n>/checks.md`, pushes the branch, opens the pull request, then records and pushes the delivery. No status is published.
- `src/ariane/tracker.py`, `Tracker`: only `read_issue`, `open_pull_request` and `file_url`. `InMemoryTracker` is the test double.
- `src/ariane/github.py`, `GitHubTracker`: REST calls through `_request`.

## Decided spec

1. The tracker interface gains `set_commit_status(sha, context, state, description, target_url)`, where `state` is `"success"` or `"failure"`. `GitHubTracker` implements it with `POST /repos/{owner}/{repo}/statuses/{sha}`, and `InMemoryTracker` records the calls.
2. After a successful delivery (the last push done, the pull request open), Ariane publishes one status per check on the pull request's head commit, the commit it pushed last:
   - `context`: `ariane/<check name>`;
   - `state`: `success` if the check passed, `failure` otherwise. An advisory check that failed is published as `failure` too: the status reports the result, and the project decides in its branch protection which ones are required;
   - `description`: the check's result detail and duration, for example `exit 0, 12.3 s`, cut to 140 characters;
   - `target_url`: the link to `work/<n>/checks.md` on the ticket branch (`Tracker.file_url`).
3. A status the tracker refuses (`TrackerError`) does not stop the ticket. It is written to the journal as a warning, and the command's summary line still reports the pull request.
4. The README says that the token needs permission to write commit statuses.

## Release note

Added: Ariane publishes each check's result as a commit status on the pull request.

## Acceptance criteria

- A delivered ticket has exactly one status per declared check on the pull request's head commit, with the context, state, description and link above.
- An advisory check that failed shows as `failure`; a delivered ticket's blocking checks all show as `success`.
- A refused status is journaled as a warning and the ticket still ends delivered, exit code 0.
- `GitHubTracker.set_commit_status` sends the documented request (method, path, JSON body); an HTTP error becomes a `TrackerError` that does not contain the token.

## Acceptance checklist

- [ ] `tests/test_flow.py` or `tests/test_flow_guards.py` covers statuses on delivery, including the advisory failure.
- [ ] A flow test covers a refused status.
- [ ] `tests/test_github.py` covers the request shape and an HTTP error, using the local stub.
- [ ] All checks in CLAUDE.md pass.

## Out of scope

- GitHub check runs and GitHub Apps.
- Statuses for a ticket that stops before delivery: nothing is pushed then.
- Pending statuses while the checks run.
