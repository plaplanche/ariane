# 0058. Review escapes per model pair and stop categories

- Status: accepted
- Date: 2026-10-20
- Capabilities: C10, C19

## Context
Ariane rests on two claims it did not measure: that a reviewer on a different model catches what
the implementer missed (C10), and that the failures that matter come from the orchestration rather
than from the code. `ariane report` (C19) gave cost, time, rounds and the first-pass verdict per
ticket, but not how often a `go` was wrong, nor why tickets stopped: C19 asks for failure causes
per ticket. Choosing a reviewer model or a risk tier without those numbers is guesswork.

## Decision
- **Verdict per review.** `Metrics.reviewed(go, findings)` writes `verdict` (`go`, `no-go`) and
  `findings` (their number, after the definition of done is settled) into the reviewer session
  that answered, the last one. A review is a reviewer session with a verdict; records from before
  this decision have none and are not counted.
- **Escape.** A record delivered green on a `go` (its last review; not a shadow ticket) escapes
  when, on its pull request (the latest from `ariane/<n>`, or from a hand takeover's branch): the
  CI was red on the reviewed head, a human (a GitHub account of type `User`, not `Bot`) left a
  "changes requested" review, or the pull request was closed without merge. An open pull request
  with nothing against it is not an escape yet; a branch without a pull request is left out. The
  escape rate is escapes over the `go` tickets the tracker described.
- **CI data.** The CI result is read from `ci_failures` in the ticket's `metrics.json`, written by
  the CI rounds when they exist (#147): a list of the failed CI checks on the reviewed head, red
  when not empty. Until then no record has it, the CI part is skipped and the report says so in
  one line.
- **Grouping and threshold.** Reviews are grouped per implementer model (the first implementer
  session's; `by hand` for a hand takeover), reviewer model and reviewer runtime. Each group shows
  reviews, tickets, `go`, findings per review and escapes; its rate is shown only over 5 tickets
  or more. When two groups or more show a rate, an "Escape rates compared:" line puts them side by
  side with their number of tickets. It is a section of the normal report, printed when a review
  with a verdict exists, rather than a separate `--escapes` flag: the report stays one command.
- **Stop categories.** Every outcome other than delivered green records `category` in
  `metrics.json`, from the fixed list `stop.CATEGORIES`: `spec` (the implementer changed no file:
  the ticket was unclear; or the issue gate refused it), `guard` (push guard,
  tree or reviewer tree changed, processes left running, records committed by the agent), `budget`
  (a cost, token, turn or time limit of a session), `runtime` (an agent CLI error, a quota, a
  login, a reviewer answer invalid twice), `checks` (blocking checks red: on the first replay, or
  still red after the fix rounds), `review` (a review still `no-go` after the rounds, or a fix round
  that changed nothing after one), `merge` (a conflict while updating the branch), `ci` (red CI
  after the CI rounds), `infra` (setup, slot, lock, a leftover tree, the tracker, git, and any
  other error). `merge` and `ci` are reserved for the `update` command and the CI rounds, which do
  not exist yet. A delivered green ticket has no `category` key. `Stop` carries its category
  (`infra` by default), so each raiser names its own; `ReviewFailed` and `verify.Refused` carry one
  too. `ariane report` counts the tickets per category, then per implementer model; a record from
  before categories is `not recorded`. A start that ends before its run exists (the issue gate,
  Ctrl-C during the issue's read, the lock, a slot, the registry, the preparation) has no ticket folder, and another run of the
  ticket may hold one: it records its category in a new folder per attempt,
  `<repo>.ariane/stopped/<n>/refused/<time>-<random>/metrics.json`, which overwrites nothing.
  The report reads those, the first-setup stops (`<repo>.ariane/stopped/<n>/metrics.json`, ADR
  0031) and the verifications that ended without committing (`<repo>.ariane/verify/<slug>/`),
  each as its own attempt: never merged with a run of the same ticket and start second.
- **Order and identity.** Only what follows the `go` makes it an escape: the reviewer session
  that answered records `at`, its time, and a "changes requested" review or a close without merge
  counts when it is at that time or later (a record from before `at` uses its `started`). The
  pull request is the branch's latest: Ariane opens one per ticket branch. The 5-ticket threshold
  counts distinct ticket numbers: several records of one ticket (hand takeovers) count once, as
  escaped if any of them escaped.
- **The tracker is read at report time.** What happened after a `go` (the owner's review, the
  merge or the close) happens after Ariane's run ended, often days later; Ariane did not see it and
  does not store it. The report asks the tracker each time (`Tracker.pull_request_state`, with the
  pull request's number, and `Tracker.changes_requested`), like the waiting time (ADR 0038), and
  posts nothing.

## Consequences
- The reviewer choice and the risk tier (#185) can be compared on numbers, per model pair and
  runtime, once enough tickets ran on each.
- A report with a tracker makes one more request per green `go` ticket for its reviews, and asks
  the pull request state of those tickets again (the waiting time asks it too); a tracker failure
  stops further requests for the run of the report.
- An interrupt (Ctrl-C) is counted as `infra`: the list is fixed and none of the other causes fits
  better; the journal still says "interrupted by the user".
- Escapes found after the merge on the base branch (reverts, later bugs) are not counted.

## Alternatives considered
- Recording the escape facts in `metrics.json` when Ariane next runs: they happen after the run,
  and the record would be stale or missing for tickets never touched again.
- Counting an escape on any `go`, including those followed by a later `no-go` in the same run: in
  `start` a `go` ends the rounds, so the last review of a delivered record is its only `go`.
- A free-text failure cause: it could not be counted or compared.
- A separate `--escapes` flag: one more option for a section that only appears when there is data.
