# Operations: running tickets day to day

How each command behaves, what it refuses, and where it leaves its records. The options of every
command are in the [command-line reference](../reference/cli.md); the log types in
[`logs.md`](../logs.md).

## The issue gate

Ariane only runs an issue that carries the label `ariane` (`tracker.ready_label`), put by a person
with write access (the owner of a personal repository, or a writer), and not changed since;
otherwise it exits 2 before creating anything. Ariane waits up to 15 seconds for GitHub to list
the label event when it lags behind the issue. Add the label to each ticket you want to run, and
add it again after any later change, comments and the pull request's own reference included (for
example before `ariane verify --issue N` or `ariane update N`)
([ADR 0032](../adr/0032-issue-gate.md)).

## `ariane start`

`ariane start 12` creates the branch `ariane/12` in a working tree beside the repository
(`<repo>.ariane/worktrees/12`), runs the setup command, one implementer session and every check.
If a blocking check fails before any review, it stops there and pushes nothing. Otherwise a
read-only reviewer on a different model reviews the delivered commit ([reviewers](reviewers.md));
on a no-go, up to two fix rounds follow, each with a fresh implementer session, a replay and a
review (a fix round that changes nothing ends the rounds, with a draft pull request). Then it
pushes the branch, opens the pull request (a draft that needs a human if the review is still
no-go) and publishes each check's result as a commit status (`ariane/<check name>`) on its head
commit.

The ticket's records are in `work/12/`: the brief, the journal (with the context given to each
agent), `checks.md`, the reviews, the status and `metrics.json` (cost, tokens, durations, fix
rounds, first-pass verdict, recurring findings and outcome, rewritten after each step). The last
of them (the status `delivered` with the pull request, and the journal's push and pull request
entries) is committed on the local branch only, after the push, so the ticket's working tree is
clean and the next push of the branch carries it. `metrics.json` also counts, in `attempts`, the
`git push` and `gh pr create` commands the agent tried and the guard violations
([ADR 0036](../adr/0036-shadow-mode-and-attempts.md)).

Each agent session stops at its limits, set per role in `[agents.<role>]`: its cost
(`max_budget_usd`), its tokens (`max_tokens`), its total time (`timeout_minutes`) and its idle time
(`idle_minutes`, 10 by default): a session that sends no event for that long is stopped as a
`timeout`, and the journal and the stop line say "no activity for <m> min (idle limit)" with the
last event ([ADR 0045](../adr/0045-idle-limit-of-agent-sessions.md)). Its work is kept on the
branch.

On Linux, Ariane is the subreaper of the processes it starts: one an agent, a setup or a check
leaves running (in its process group or a new session) is killed as soon as that command ends,
even when it fails or is interrupted, counted in `metrics.json` and stops the ticket. On macOS and
Windows there is no such detection yet.

### Restarting a stopped ticket

A ticket that stopped (a blocking check, a budget stop, a reviewer failure) or whose process died
(Ctrl-C, a machine restart) leaves its working trees and its branch, so `ariane start 12` refuses
it and names `--restart`. `ariane start 12 --restart` removes the ticket's working trees (`12`,
`12-review`, `12-replay-*`), keeps the branch `ariane/12` as `ariane-restarted/12-<UTC time>`
(kept, never deleted: what the previous run committed stays there) and starts the ticket as a new
run, whose journal opens with what was removed and kept. Files the previous run left uncommitted in
its working tree `12`, modified or untracked (not ignored), and staged content, are first saved in
commits on top of the kept branch, written before any tree is removed. It refuses while another
`ariane start 12` runs (each run holds `<repo>.ariane/locks/12.lock`), when `ariane/12` is already
on the remote, and with `--shadow` (remove the clone instead). `ariane report` counts the time from
the previous stop to the restart in the human time
([ADR 0047](../adr/0047-restart-a-stopped-ticket.md)).

PowerShell:

```powershell
ariane start 12 --restart
if ($LASTEXITCODE -ne 0) { ariane status 12 }
```

bash:

```bash
ariane start 12 --restart || ariane status 12
```

## `ariane start --shadow` and `ariane judge`

`ariane start --shadow 12` runs the same flow in a separate clone, `<repo>.ariane/shadow/12`, cut
from your repository's last fetched `origin/<base branch>` with `origin` removed: your repository
is only read, and nothing is pushed, no pull request opened, no status or comment posted. It ends
with the clone's `work/12/` to read. Remove the clone to start the ticket over. Then say what you
think of the diff and how long it took you: `ariane judge 12 accept --minutes 20 --note "fine"` (or
`reject`) records it in the shadow ticket's `metrics.json`; judging again keeps the earlier
judgement in `judgements_before`. The second-user path is in the
[README](../../README.md#measure-ariane-on-your-project-shadow-mode).

## `ariane verify`

`ariane verify <branch> [--issue N]` checks and reviews a local branch finished by hand: a clean
replay of the checks (each in its own tree), one review, then `work/verify/<branch>/review.md`,
`checks.md` and `metrics.json` committed on the branch (never pushed). It exits 0 only on a `go`
with green blocking checks; the issue's text goes to the reviewer with `--issue`, else the branch's
commit messages. A refused run keeps its `metrics.json` in `<repo>.ariane/verify/<branch>/`.

## `ariane update`: bring a delivered ticket up to date

When the base branch has moved after a pull request was opened, `ariane update <n>` merges it into
`ariane/<n>` (a merge commit, never a rebase or a force-push), in the ticket's working tree,
replays the checks on the merge commit, runs one review, and on `go` with green blocking checks
pushes the branch again: the pull request updates by itself, with one status per check on the new
head ([ADR 0033](../adr/0033-branch-update-and-ticket-dependencies.md)). It reads the issue through
the issue gate, so add the label `ariane` again first (the pull request referenced the issue).

It refuses, before changing anything, a ticket whose pull request is merged, closed or missing,
whose working tree is missing, dirty or on another branch, whose `work/<n>/` holds a folder or a
link (the update would remove it), whose base branch changed `work/<n>/`, or whose local branch has
commits the remote branch lacks beyond Ariane's own records in `work/<n>/`. When the base branch is
merged already it says so and writes nothing.

A merge conflict, or a blocking check the merge broke, goes to one implementer session whose task
it is (the conflicting paths, or the failing checks' output); Ariane commits the merge (both
parents kept) or the fix as `#<n>: fix after merging <base>`, then replays and reviews; a red check
or a `no-go` then gets one fix round, as in `ariane start`. A session that leaves a path unmerged or
a conflict marker line (in a file or staged) stops the update with the merge left in progress for
you, nothing committed. Still red or `no-go` after that round, or a `no-go` on a clean merge, stops
with status `needs a human` and pushes nothing; the review's record continues the ticket's
numbering (`review-<k>.md`) and `metrics.json` counts the `updates`.

PowerShell:

```powershell
$env:GH_TOKEN = "<a token with access to the repository>"
ariane update 12
ariane status 12
```

bash:

```bash
export GH_TOKEN="<a token with access to the repository>"
ariane update 12
ariane status 12
```

## Several tickets: `ariane next` proposes the next one

To run tickets one after another, or side by side, label the issues `ariane-next`
(`[tracker] next_label`) in the order you want them: that is the queue. A line `Needs #12` (or
`Needs #12 and #14`) in an issue's body makes it wait until each issue named is closed as
completed. `ariane next` looks at the first 5 issues of the queue (`[next] look_ahead`), the
running tickets left out, and says for each whether it can start now and why not:

```text
Running: #12.
- #13: waits on #12
- #14: shares src/app/cli.py with running #12
- #15: can start
Next: #15 (no shared file with #12). Start it with ariane next --start.
```

An issue is expected to touch the file paths written in its body (`src/app/cli.py`, a folder
`docs/adr/`), and for a module file (`docs/architecture/modules/cli.md`, or just `cli.md`) the
module's source `src/<package>/cli.py` and its tests by name; `[next.paths]` adds globs per label.
A running ticket touches what its branch changed plus its own expected files, read from its issue
even once it left the queue. Two globs share a path when one path can match both (`docs/**` and
`docs/architecture/**`). An issue already started (it has a branch `ariane/<n>`) is never
proposed. No free run slot, a last run stopped on its agent's quota, or a running ticket whose
files cannot be read yet (it is still preparing its branch) proposes nothing and says what to do.

`ariane next` starts nothing. `ariane next --start` proposes again and, only if the proposal is the
one last printed, removes and adds the issue's `ariane` label (as a maintainer would, so the issue
gate accepts it; the token then needs issues: write) and runs `ariane start <n>` in the
background, detached from the terminal. It waits until that ticket registers as running, so a
second `--start`, or an `ariane start` by hand, never slips in between; then it prints the ticket
number, where its journal will be, and its output file (`<repo>.ariane/logs/<n>.out`). A start
consumes the confirmation: run `ariane next` again before the next `--start`. Every proposal and
start, with the reasons for the other issues and who confirmed, is appended to
`<repo>.ariane/next.md`; a start whose record could not be written is recorded by the next
`ariane next` ([ADR 0060](../adr/0060-next-ticket-proposal.md)). The lock and the reservations are
local to `<repo>.ariane/`: two machines (or two cloud sessions) can still start the same ticket,
and the collision is seen at the push.

```toml
[tracker]
next_label = "ariane-next"

[next]
look_ahead = 5
paths = { docs = ["docs/**"] }  # an issue labelled `docs` is expected to touch docs/
```

## Several runs on one repository: the push guard

Only Ariane runs git commands in the repository while a ticket runs. Several tickets may run at
once on one repository (one `ariane start` each): each run is registered in
`<repo>.ariane/runs/<n>` while it lasts. Ariane checks that the agent changed nothing outside the
ticket branch (git configuration, hooks, local branches, the remote); the only change it tolerates
is another registered run's own bookkeeping: its branch `ariane/<m>` and that branch's `remote` and
`merge` keys, and only for a run Ariane saw running. Anything else, even another key of that
branch, stops the ticket. A merge on the base branch (a fast-forward) does not stop the ticket; any
other remote change does: a created, deleted or rewritten branch or tag, a base branch that did not
fast-forward, or any change to the ticket's branch. The stop line names the refs (ADR 0017).
Another run's fetch of a base branch that advanced by a merge does not stop the ticket either: the
base's tracking ref may fast-forward to the commit the remote's base points to, and the ticket
keeps the base it started from; any other move of that ref stops it (ADR 0055).

Only Ariane pushes, with the tracker token sent as an HTTP authorization header for that one push
(the machine's credential helpers are off). Without a token, or if that push is refused for
authentication, Ariane pushes once more without the header and journals which way it went.

**In a cloud sandbox** whose proxy supplies its own credentials, an agent's push is detected after
the session, not prevented (ADR 0017): the agent holds no credential, but the network gives it
one. This is the environment where the push guard is weakest. To check what your proxy does, run
`git push --dry-run` or a push of a throwaway branch from a session without the token and see
whether it is accepted.

## `ariane report`

`ariane report [--since YYYY-MM-DD]` summarises cost, agent time, rounds and first-pass verdicts
per ticket from the `metrics.json` files in the checkout and in the ticket worktrees (which hold
the full replay after delivery). It also gives the two numbers of the success measure:

- **Human time**: a delivered ticket's waiting time from its pull request's opening to its merge or
  close, read from the tracker with the token ("not available" without it), plus each stop to the
  next `ariane verify`; a shadow ticket's minutes from `ariane judge`.
- **Gates bypassed**: hand takeovers, blocking checks red at delivery, a pull request merged while
  its last review is no-go.

Shadow tickets show their judgement, the accept rate, the agents' push and pull-request attempts,
and `shadow pass: yes|no` over the last 10 (no attempt, no violation, at least 8 accepted).

A "Selective checks" line gives the tickets with selection and their replay time, the selective
rounds' time against the full replays' time on the sampled tickets (the time saved), the full
replays run, the escapes and the escape rate (escapes / full replays; [checks](checks.md#full-replay-measuring-what-selection-misses)).

The review escapes count, per implementer model, reviewer model and reviewer runtime, the reviews,
`go` verdicts, findings per review and escapes: a `go` followed on its pull request by a red CI on
the reviewed head, a human "changes requested" review, or a close without merge (read from the
tracker at report time; the CI part is skipped, and said so, until CI results are recorded). The
escape rate (escapes / `go`) is shown from 5 tickets, side by side when two pairs have one. Every
ticket that did not end delivered green records a stop category in `metrics.json` (`spec`,
`guard`, `budget`, `runtime`, `checks`, `review`, `merge`, `ci`, `infra`), counted in total and per
implementer model (ADR 0058).

## Logs

Technical logs go to standard error and to `<repo>.ariane/logs/<n>.log`, at the level of
`--log-level` or `ARIANE_LOG_LEVEL` (default warning). The catalogue of log types is
[`logs.md`](../logs.md), generated from the code.
