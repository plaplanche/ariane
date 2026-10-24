# Ariane

**Ariane is a local command-line orchestrator that takes a labelled GitHub issue to a reviewed
pull request with AI coding agents, while the human keeps deciding and merging.** A Claude Code
session implements the ticket; Ariane replays the checks itself, has the change reviewed by a
different model (on Claude Code, Codex, pi or opencode), measures the ticket and delivers one
branch and one pull request. The name comes from Ariadne's thread (*le fil d'Ariane*): you never
lose the thread of your own code.

It runs on Windows, macOS and Linux, from your own machine, with the agent CLIs and logins you
already have. Free software under the AGPL.

## Why Ariane exists, and what it has shown so far

**First, an exploration.** Ariane is its owner's own exploration of one question: what does an
engineering process look like when one developer drives many coding agents, and which of its
gates can be enforced by code rather than asked for in a prompt? That value is already there.
Since slice 2, Ariane's own tickets go through Ariane, and each ticket leaves a readable record
(`work/<n>/`: brief, journal, checks, reviews, `metrics.json`). The ideas it has tried out stand on
their own, with or without the tool:

- deterministic proof before opinion: the checks are replayed outside the agent's session, and
  each result is a commit status;
- an executable definition of done, given to the implementer and checked item by item by a
  reviewer on a different model, from another vendor if you choose;
- a measure per ticket (cost, rounds, first-pass verdict, human time, gates bypassed) as the basis
  for deciding how to use agents.

**Then, values still to be demonstrated.** None of the following is shown yet; each names what
would show it.

| Claimed value | What we know today | What would demonstrate it |
| --- | --- | --- |
| Faster or cheaper than an agent alone | **Not true for one person on a well-specified project.** On the [benchmark](docs/benchmark.md), Claude Code alone reached the same hidden acceptance, two to three times faster; Ariane cost less than Opus alone but more than Sonnet alone. Ariane is not pitched on speed. | Running the benchmark again after the fixes it called for; until then, the claim is dropped. |
| Trust for someone who merges many agents' pull requests | The checks are replayed and the review is independent; the review caught real defects before a human looked, but they did not change the benchmark's final result. | The benchmark's next lot: two people (or sessions) in parallel on one repository, where Ariane is expected to pay off. |
| Works on someone else's project | Almost every ticket so far ran on Ariane itself, in a Linux cloud sandbox. | Slice 4's gate: a second user installs Ariane on macOS and runs 10 tickets in shadow mode on their own project (below), compared on human time and gates bypassed. |
| Keeps the human understanding their own code | Not built: approvals before code, mastery checks and learnings are slices 5 to 8. | Those slices, measured with the same two numbers. |
| Fits teams under constraints (everything local, a reviewer from another vendor required by policy) | Built for it, never tested in such a team. | A team in that situation running the shadow mode. |

## What Ariane protects against, and what it does not

Ariane guards against an agent's **mistakes**, not against a hostile agent: everything runs as
your user, without an operating-system sandbox, until the security slice (slice 9).

- **No credentials for the agent.** Agents get an allow list of environment variables; the
  tracker token is removed from Ariane's own environment once read and only used for the tracker
  and the push. On Linux Ariane's process is not dumpable; on macOS, Windows and as root, a
  process of the same user may still read its memory (ADR 0017).
- **No push by the agent.** Agents hold no git credential and only Ariane pushes. A push guard
  stops the ticket if an agent touches git configuration, refs or hooks. In a cloud sandbox whose
  proxy supplies its own credentials, an agent's push is **detected after the session, not
  prevented** ([operations](docs/guide/operations.md#several-runs-on-one-repository-the-push-guard)).
- **No word taken for it.** Ariane replays the checks itself; the agent saying the tests pass
  counts for nothing. What the replay cannot run (a browser, a GPU) is declared and shown to the
  reviewer as untested, not verified ([checks](docs/guide/checks.md)).
- **No leftover processes, on Linux only.** A process an agent or a check leaves running is killed
  and stops the ticket; macOS and Windows have no such detection yet.
- **Basic redaction.** What Ariane posts and records is redacted against known values and common
  token formats; it is not a complete secret scanner, and the detail of a failure printed on the
  terminal is not redacted.

The residuals the owner accepted are written in the ADRs; those written as an item starting
with `- **Accepted residual.**` are also given to the reviewer.

## How a ticket runs

```mermaid
flowchart LR
  issue[Issue labelled ariane] --> tree[Worktree ariane/n]
  tree --> impl[Implementer session<br/>Claude Code]
  impl --> checks[Checks replayed<br/>one clean tree each]
  checks -->|blocking check red before any review| stop[Stop, nothing pushed]
  checks --> review[Read-only review<br/>different model]
  review -->|no-go, up to 2 fix rounds| impl
  review -->|go| pr[Push, pull request,<br/>one status per check]
  review -->|still no-go| draft[Draft pull request<br/>needs a human]
  pr --> human[You merge]
  draft --> human
```

1. **The gate.** Ariane only runs an issue labelled `ariane` by a person with write access and not
   changed since; otherwise it exits 2 before creating anything.
2. **Isolation.** Branch `ariane/<n>` in a working tree beside the repository
   (`<repo>.ariane/worktrees/<n>`), the setup command, filtered environment, pushing blocked.
3. **Implementation.** A fresh Claude Code session, with the ticket as untrusted data and limits on
   cost, tokens, total time and idle time. Ariane commits, never the agent.
4. **Checks.** Each check of `ariane.toml` is replayed in its own clean tree at the commit. A red
   blocking check before any review stops the ticket.
5. **Review.** A read-only reviewer on a different model answers `go` or `no-go` against the ticket
   and the definition of done ([reviewers](docs/guide/reviewers.md)). A `no-go` gets up to two fix
   rounds.
6. **Delivery.** One push, one pull request (a draft if still `no-go`), one commit status per
   check, and the ticket's records in `work/<n>/`. You merge.

## Get started from Claude Code

The shortest path to Ariane on your own project is to drive it from a Claude Code session opened
in that project: you give the prompts below, Claude Code runs the commands, and you read the pull
request and merge. Start with Claude models only (Sonnet implements, Opus reviews), then move the
review to Codex once the first tickets go through.

### Before the session

You need Python 3.11 or later, [uv](https://docs.astral.sh/uv/), git, and Claude Code (`claude`)
logged in. Create a fine-grained GitHub token limited to the one repository, with **contents,
pull requests and commit statuses: write; issues: read** (issues: write if you use
`ariane next --start`, which relabels the issue); no workflows, no administration. Set it in the
shell that starts Claude Code, so that the commands Claude Code runs inherit it; Ariane removes it
from its own environment once read and never gives it to an agent.

PowerShell:

```powershell
$env:GH_TOKEN = "<the token>"
claude
```

bash:

```bash
export GH_TOKEN="<the token>"
claude
```

In a cloud session, set `GH_TOKEN` in the environment's variables instead.

### Step 1: Sonnet implements, Opus reviews

**1. Install Ariane.** Prompt:

```text
Install Ariane with `uv tool install git+https://github.com/plaplanche/ariane`, then run
`ariane --version` and tell me the version.
```

**2. Write the configuration.** Prompt (replace the repository name):

```text
Create ariane.toml at the root of this repository, from the minimal configuration in Ariane's
README (https://github.com/plaplanche/ariane#get-started-from-claude-code):
tracker.repository = "<owner>/<repository>", the implementer on Claude Code with
claude-sonnet-5-5, the reviewer on Claude Code with claude-opus-5-5 and the tools Read, Glob,
Grep. Set project.base_branch to our default branch, project.setup to the command that installs
this project, and add one [[checks]] entry per command our CI runs (lint, types, tests), as
lists of arguments run from the repository root. Run each check command once to see that it
passes on the default branch. Commit ariane.toml on the default branch, push it, and add nothing
else.
```

The minimal configuration it starts from:

```toml
[project]
base_branch = "main"
setup = ["uv", "sync"]

[tracker]
kind = "github"
repository = "your-account/your-repository"
token_env = "GH_TOKEN"

[agents.implementer]
runtime = "claude-code"
model = "claude-sonnet-5-5"
tools = ["Read", "Edit", "Write", "Glob", "Grep", "Bash"]
max_budget_usd = 5.0
timeout_minutes = 30

[agents.reviewer]
runtime = "claude-code"
model = "claude-opus-5-5"
tools = ["Read", "Glob", "Grep"]
max_budget_usd = 3.0
timeout_minutes = 20

[[checks]]
name = "tests"
command = ["uv", "run", "pytest", "-q"]
```

[`docs/ariane.example.toml`](docs/ariane.example.toml) comments every other key (definition of
done, documentation, selective checks, caches, sensitive paths, the queue), Ariane's own
[`ariane.toml`](ariane.toml) is a complete example, and the
[JSON Schema](docs/reference/ariane.toml.schema.json) lists them all. A configuration error stops
`ariane start` with exit code 2 before it creates anything, naming the key.

**3. Write a small ticket and label it yourself.** On GitHub, open an issue for a change of a few
hundred lines at most, with what is wanted, its acceptance criteria and what is out of scope.
Then add the label `ariane` yourself, from your account: Ariane only runs an issue labelled by a
person with write access, and not changed since (add the label again after any edit or comment).

**4. Run the ticket.** Prompt (replace 12 with the issue's number):

```text
Run `ariane start 12` in the background: it can take 10 to 60 minutes, longer than one command's
time limit. When it ends, give me its last line, the output of `ariane status 12`, and a summary
of the ticket's records in work/12/ of its working tree (../<this folder>.ariane/worktrees/12):
the checks, each review's verdict and blocking findings, the cost in metrics.json, and the pull
request's link. Do not push, merge, relabel or change anything yourself.
```

Ariane works beside the repository (`../<repo>.ariane/`), so Claude Code may ask you to allow
access to that folder. The ticket ends in one of three ways:

- **A pull request**: the checks passed and the reviewer said `go`. Read it and merge it.
- **A draft pull request that needs a human**: the review was still `no-go` after two fix rounds.
  Finish the branch by hand (or with Claude Code), then have it checked again with the prompt
  `Run ariane verify ariane/12 --issue 12 and summarise the review.` after labelling the issue
  `ariane` again.
- **A stop, nothing pushed**: a blocking check failed before any review, a limit was reached or
  the gate refused the issue; the last line says why and what to do next. A stopped ticket starts
  over with `ariane start 12 --restart`, which keeps the previous branch.

Run a few tickets this way before changing the configuration. `ariane report` sums up their cost,
rounds and first-pass verdicts.

### Step 2: the review on Codex

A reviewer from another vendor is less likely to share the implementer's blind spots. Ariane's own tickets
run with Opus implementing and Codex reviewing (ADR 0044). The reviewer runs on the
[Codex CLI](https://github.com/openai/codex), logged in with a ChatGPT plan, so its reviews are
covered by the plan.

**1. Install and log in to Codex, yourself.** Install the Codex CLI following its own
instructions, check that `codex --version` works, then log in once from a terminal (or from
Claude Code with `!` before the command): `codex login --device-auth`, with your ChatGPT account.
The login stays in `~/.codex/auth.json`, which Ariane never reads; keep it private, like a
password. In a cloud session that file is lost with the container unless the environment keeps
it, so you log in again in each new session.

**2. Move the reviewer to Codex.** Prompt (choose the Codex model your plan offers):

```text
In ariane.toml, change [agents.reviewer] to runtime = "codex" and model = "<a Codex model>",
keeping its tools, max_budget_usd and timeout_minutes. Change the implementer's model to
claude-opus-5-5. Commit and push on the default branch, nothing else.
```

The result:

```toml
[agents.implementer]
runtime = "claude-code"
model = "claude-opus-5-5"
tools = ["Read", "Edit", "Write", "Glob", "Grep", "Bash"]
max_budget_usd = 10.0
timeout_minutes = 30

[agents.reviewer]
runtime = "codex"
model = "<a Codex model>"
tools = ["Read", "Glob", "Grep"]
max_budget_usd = 3.0
timeout_minutes = 20
```

On Codex, the read-only sandbox restricts the reviewer, not `tools`. Opus as implementer is a
choice, not a requirement: Sonnet can keep implementing.

**3. Run the next ticket** with the same prompt as in step 1. A Codex login that is missing, or
made with an API key instead of ChatGPT, stops the ticket when the review starts and says how
to fix it; a plan whose usage limit is reached stops it with "reviewer quota reached", never a `no-go`:
restart it after the reset time. To be billed per token instead, set `api_key_env` in
`[agents.reviewer]`; [reviewers](docs/guide/reviewers.md#reviewer-on-codex) has the details, and
the pi and opencode reviewers.

## Commands

Every command exits 0 on success, 1 when the work stopped or was refused (the last line says why
and what to do next), 2 on a usage or configuration error or an issue the gate refused; `start`, `update` and
`verify` exit 130 on Ctrl-C. Options are in the [command-line reference](docs/reference/cli.md); behaviour in
[operations](docs/guide/operations.md).

| Command | What it does |
| --- | --- |
| `ariane start <n>` | Runs the ticket of issue `n` up to its pull request; `--restart` starts a stopped ticket over, keeping its branch. Exit 1 also when the pull request is a draft that needs a human. |
| `ariane start --shadow <n>` | The same flow in a separate clone: nothing pushed, posted or written to your repository. |
| `ariane judge <n> accept\|reject --minutes N` | Records your verdict and time on a shadow ticket. |
| `ariane status <n>` | Shows a ticket's state, read from its folder. |
| `ariane verify <branch> [--issue N]` | Checks and reviews a branch finished by hand, then commits the records on it (never pushes). Exit 0 only on `go` with green blocking checks. |
| `ariane update <n>` | Merges the base branch into a delivered ticket's branch, replays, reviews, and pushes on `go`. |
| `ariane next [--start]` | Proposes the next ticket of the `ariane-next` queue that can start beside the running ones; `--start` starts it. Exit 1 when nothing can start. |
| `ariane report [--since YYYY-MM-DD]` | Cost, agent time, rounds, first-pass verdicts, human time, gates bypassed, shadow results, escapes. |

## Measure Ariane on your project (shadow mode)

This is the path for a second user on macOS (it works the same on Linux and Windows) who wants to know whether Ariane
does at least as well as their current process, on their own project. Shadow mode never pushes,
opens a pull request, sets a status, posts a comment or writes to your repository: it works in a
separate clone.

1. **Install Ariane** ([ADR 0021](docs/adr/0021-second-user-distribution-and-contributions.md)).
2. **Configure it.** Start from the minimal `ariane.toml` above, or download
   [`docs/ariane.example.toml`](docs/ariane.example.toml) as `ariane.toml` (commands below), and
   set `repository`, the checks and the agents.
3. **Label each ticket** `ariane`, by a person with write access, and again after any later edit
   or comment; otherwise `ariane start` refuses the ticket and exits 2 (ADR 0032).
4. **Per ticket**, fetch, run `ariane start --shadow <n>`, read the clone's `work/<n>/`
   (`<repo>.ariane/shadow/<n>/work/<n>/`), then record your verdict and the minutes you spent with
   `ariane judge <n> accept|reject --minutes N`.
5. **After the tickets**, run `ariane report`.

bash (macOS, Linux):

```bash
uv tool install git+https://github.com/plaplanche/ariane
export GH_TOKEN="<a token with read access to issues>"
curl -fsSL -o ariane.toml https://raw.githubusercontent.com/plaplanche/ariane/main/docs/ariane.example.toml   # then edit it
git fetch origin
ariane start --shadow 12
ariane judge 12 accept --minutes 20   # or reject
ariane report
```

PowerShell:

```powershell
uv tool install git+https://github.com/plaplanche/ariane
$env:GH_TOKEN = "<a token with read access to issues>"
Invoke-WebRequest https://raw.githubusercontent.com/plaplanche/ariane/main/docs/ariane.example.toml -OutFile ariane.toml   # then edit it
git fetch origin
ariane start --shadow 12
ariane judge 12 accept --minutes 20   # or reject
ariane report
```

**Pass criteria over 10 tickets:** no agent push or pull-request attempt, no write to real data,
no guard violation, Ariane's diff judged acceptable by you in at least 8, cost and duration
recorded. `ariane report` prints `shadow pass: yes|no` over the last 10 tickets (no attempt, no
violation, at least 8 accepted); cost, duration and real data are for you to check.

**Keep a short log of your current process** for the same tickets (your minutes per merged pull
request, and the steps skipped or gates bypassed). The comparison is on two numbers: human time
per merged pull request and the count of steps skipped or gates bypassed; Ariane's come from
`ariane report`, and the owner decides on them (spec, "Measuring Ariane").

## Status

Slices 1 to 3 are done: the ticket flow, dogfooding, and the vendor-neutral review with fix rounds
and `ariane verify`. Slice 4 (measurement and shadow mode) is built; its gate waits for the second
user's shadow run. Of slice 5, branch updates (`ariane update`) and a queue that honours `Needs #N`
(`ariane next`) are delivered; `ariane start` does not check dependencies yet. Approved briefs and
designs before the code, vertical slices, the per-ticket budget and the approve and revise
commands are not started, and depth by risk (C3) is partly built (selective checks, small
review). Slices 6 to 9 (stronger checks, mastery, learnings, security)
are not started. The roadmap is in [`docs/spec.md`](docs/spec.md).

## Documentation

- [`docs/spec.md`](docs/spec.md): vision, capabilities, non-functional requirements, roadmap and
  founding decisions.
- [`docs/guide/`](docs/guide/): [checks](docs/guide/checks.md) (selection, risk tiers, full
  replay, parallel checks, caches, `ARIANE_SLOT`, environment),
  [reviewers](docs/guide/reviewers.md) (what the review checks, isolation, Codex, pi, opencode),
  [operations](docs/guide/operations.md) (issue gate, restart, shadow, verify, update, next, push
  guard, report, logs).
- [`docs/architecture/`](docs/architecture/README.md): how Ariane works, in Mermaid diagrams from
  the system landscape to each module.
- [`docs/reference/`](docs/reference/cli.md) and [`docs/logs.md`](docs/logs.md): the command-line
  reference, the JSON Schema of `ariane.toml` and the catalogue of log types, generated by
  `scripts/generate_docs.py` (never edited by hand).
- [`docs/benchmark.md`](docs/benchmark.md): Ariane against Claude Code alone on a reference
  project.
- [`docs/adr/`](docs/adr/): architecture decision records, written as the implementation goes.

## Develop Ariane

From a clone, `uv sync` installs the development tools; the checks are listed in
[`CLAUDE.md`](CLAUDE.md) ("Checks"). `uv run pytest` runs the tests in parallel, one worker per
CPU (`pytest-xdist`, `-n auto`); `uv run pytest -n 0` runs them serially, for example to debug one
test with `pdb`. CI runs the checks with Python 3.13 on Windows, macOS and Linux, and with Python
3.11, the minimum, on Linux only ([ADR 0048](docs/adr/0048-parallel-tests-and-ci-matrix.md)). The
tests' git project is built once per worker and copied for each test
([ADR 0049](docs/adr/0049-template-project-and-windows-shards.md)). Windows CI runs the tests in
two shards, `uv run pytest --splits 2 --group 1` (or `2`) with `--splitting-algorithm
least_duration`, balanced from `.test_durations` (refresh it with
`uv run pytest --store-durations`); every other CI job runs the whole suite. The
`check-statuses.yml` workflow is specific to Ariane's own repository
([checks](docs/guide/checks.md#statuses-published-from-ci)).

## License

Ariane is free software under the [GNU Affero General Public License v3.0 only](LICENSE)
(`AGPL-3.0-only`): you may use, study, modify and share it, and anyone who offers a modified
Ariane to others, including as a network service, must publish their changes under the same
license. Other licensing terms can be arranged with the copyright holder
([ADR 0008](docs/adr/0008-license.md), [ADR 0021](docs/adr/0021-second-user-distribution-and-contributions.md)).
Fixes are sent as issues.
