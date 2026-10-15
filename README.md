# Ariane

Ariane turns tickets into reviewed pull requests with AI coding agents, while the human keeps
deciding, understanding and approving. The name comes from Ariadne's thread (*le fil d'Ariane*):
you never lose the thread of your own code.

**Status:** slice 3 (review, vendor-neutral) is done: `ariane start <issue>` takes a GitHub issue to a
pull request whose checks Ariane replayed in a clean tree and that a read-only reviewer on a
different model approved, after up to two fix rounds (`[agents.reviewer]` in `ariane.toml`; the
reviewer can run on Claude Code or opencode). `ariane verify <branch>` gives a branch finished by
hand the same checks and review. Slice 4, measurement and shadow mode, is next, then approvals
(slice 5) (see the roadmap in [`docs/spec.md`](docs/spec.md)).

## Try it

Requirements: Python 3.11 or later, [uv](https://docs.astral.sh/uv/), git, and Claude Code
(`claude`) logged in. From the repository to work on, with an `ariane.toml` at its root (see
[ADR 0003](docs/adr/0003-configuration-file.md) and Ariane's own [`ariane.toml`](ariane.toml)):

PowerShell:

```powershell
uv tool install git+https://github.com/plaplanche/ariane
$env:GH_TOKEN = "<a token with access to the repository>"
ariane start 12
ariane status 12
ariane verify my-branch --issue 12
```

bash:

```bash
uv tool install git+https://github.com/plaplanche/ariane
export GH_TOKEN="<a token with access to the repository>"
ariane start 12
ariane status 12
ariane verify my-branch --issue 12
```

The reviewer loads nothing from the tree under review (no hooks, settings or instruction files; ADR 0031): a Claude Code reviewer's `tools` are a subset of `Read`, `Glob`, `Grep`, and it gets the base branch's `CLAUDE.md` in its prompt as data.

### Reviewer on opencode

The reviewer can run on [opencode](https://opencode.ai) (install it separately and put `opencode`
on the PATH) with another vendor's model: set `runtime = "opencode"`, `model = "<provider>/<model>"`
and `tools = ["read", "glob", "grep"]` in `[agents.reviewer]`, and export the provider's key (for
example `OPENAI_API_KEY`). The implementer stays on Claude Code. `ARIANE_CONFIG` names a
configuration file to read instead of `ariane.toml` for one run (it does not reach the agents or
the checks);
[`docs/ariane.opencode-reviewer.example.toml`](docs/ariane.opencode-reviewer.example.toml) is Ariane's
own configuration with the reviewer on opencode (ADR 0029).

PowerShell:

```powershell
$env:OPENAI_API_KEY = "<the provider's key>"
$env:ARIANE_CONFIG = "docs/ariane.opencode-reviewer.example.toml"
ariane verify my-branch
Remove-Item Env:ARIANE_CONFIG
```

bash:

```bash
export OPENAI_API_KEY="<the provider's key>"
ARIANE_CONFIG=docs/ariane.opencode-reviewer.example.toml ariane verify my-branch
```

For a project other than Ariane, start from [`docs/ariane.example.toml`](docs/ariane.example.toml):
copy it to `ariane.toml` at the root of your repository and adapt it.

Ariane only runs an issue that carries the label `ariane` (`tracker.ready_label`), put by a person
with write access (the owner of a personal repository, or a writer), and not changed since;
otherwise it exits 2 before creating anything. Add the label to each ticket you want to run, and
add it again after any later change, comments and the pull request's own reference included (for
example before `ariane verify --issue N`) ([ADR 0032](docs/adr/0032-issue-gate.md)).

`ariane start` creates the branch `ariane/12` in a working tree beside the repository
(`<repo>.ariane/worktrees/12`), runs the setup command, one implementer session and every check. If a blocking check fails
before any review, it stops there and pushes nothing. Otherwise a read-only reviewer on a
different model reviews a clean replay; on a no-go, up to two fix rounds follow, each with a fresh
implementer session, a replay and a review. Then it pushes the branch, opens the pull request (a
draft that needs a human if the review is still no-go) and publishes each check's result as a
commit status (`ariane/<check name>`) on its head commit. The ticket's records are in `work/12/`, including `work/12/metrics.json`: cost, tokens, durations,
fix rounds, first-pass verdict and outcome of the ticket, rewritten after each step.
`work/12/metrics.json` also counts, in `attempts`, the `git push` and `gh pr create` commands the agent tried and the guard violations ([ADR 0036](docs/adr/0036-shadow-mode-and-attempts.md)).

**Shadow mode** measures Ariane while your current process does the real work. `ariane start --shadow 12`
runs the same flow in a separate clone, `<repo>.ariane/shadow/12`, cut from your repository's last
fetched `origin/<base branch>` with `origin` removed: your repository is only read, and nothing is
pushed, no pull request opened, no status or comment posted. It ends with the clone's
`work/12/` to read. Remove the clone to start the ticket over. Then say what you think of the diff and how long it took
you: `ariane judge 12 accept --minutes 20 --note "fine"` (or `reject`) records it in the shadow
ticket's `metrics.json`; judging again keeps the earlier judgement in `judgements_before`.

PowerShell:

```powershell
git fetch origin
ariane start --shadow 12
```

bash:

```bash
git fetch origin
ariane start --shadow 12
```

A GitHub Actions workflow (`check-statuses.yml`) also publishes these statuses from the committed
report, including when Ariane cannot (for example from a cloud session).
`ariane verify <branch> [--issue N]` checks and reviews a local branch finished by hand: a clean
replay of the checks, one review, then `work/verify/<branch>/review.md`, `checks.md` and `metrics.json` committed
on the branch (never pushed). It exits 0 only on a `go` with green blocking checks; the issue's
text goes to the reviewer with `--issue`, else the branch's commit messages.
`ariane report [--since YYYY-MM-DD]` summarises cost, agent time, rounds and first-pass verdicts per
ticket from the `metrics.json` files in the checkout. It also gives the two numbers of the success
measure: human time (a delivered ticket's waiting time from its pull request's opening to its merge
or close, read from the tracker with the token, "not available" without it, plus each stop to the
next `ariane verify`; a shadow ticket's minutes from `ariane judge`) and gates bypassed (hand
takeovers, blocking checks red at delivery, a pull request merged while its last review is no-go).
Shadow tickets show their judgement, the accept rate, the agents' push and pull-request attempts, and
`shadow pass: yes|no` over the last 10 (no attempt, no violation, at least 8 accepted).
The token needs permission to write commit statuses (for a fine-grained token, "Commit statuses:
read and write"), on top of reading issues and writing pull requests.

- [`docs/spec.md`](docs/spec.md): vision, functional specification (capabilities C1 to C26),
  non-functional requirements, roadmap and founding decisions.
- [`docs/architecture/`](docs/architecture/README.md): how Ariane works, in Mermaid diagrams from
  the system landscape to each module.
- [`docs/reference/`](docs/reference/cli.md): the command-line reference and the JSON Schema of
  `ariane.toml`, generated by `scripts/generate_docs.py` (never edited by hand).
- [`docs/logs.md`](docs/logs.md): the catalogue of log types, generated the same way. Technical logs
  go to standard error and to `<repo>.ariane/logs/<n>.log`, at the level of `--log-level` or
  `ARIANE_LOG_LEVEL` (default warning).
- [`docs/adr/`](docs/adr/): architecture decision records, written as the implementation goes.

## While a ticket runs

Nobody runs git commands in the repository while a ticket runs. Ariane checks that the agent
changed nothing outside the ticket branch (git configuration, hooks, local branches, the
remote). A merge on the base branch (a fast-forward) does not stop the ticket; any other remote
change does: a created, deleted or rewritten branch or tag, a base branch that did not
fast-forward, or any change to the ticket's branch. The stop line names the refs (ADR 0017).

Only Ariane pushes, with the tracker token sent as an HTTP authorization header for that one push
(the machine's credential helpers are off). Without a token, or if that push is refused for
authentication, Ariane pushes once more without the header and journals which way it went.

In a cloud sandbox whose proxy supplies its own credentials, an agent's push is detected after
the session, not prevented (ADR 0017). To check what your proxy does, run `git push --dry-run`
or a push of a throwaway branch from a session without the token and see whether it is accepted.

## License

Ariane is free software under the [GNU Affero General Public License v3.0 only](LICENSE)
(`AGPL-3.0-only`): you may use, study, modify and share it, and anyone who offers a modified
Ariane to others, including as a network service, must publish their changes under the same
license. Other licensing terms can be arranged with the copyright holder
([ADR 0008](docs/adr/0008-license.md), [ADR 0021](docs/adr/0021-second-user-distribution-and-contributions.md)).
Fixes are sent as issues.
