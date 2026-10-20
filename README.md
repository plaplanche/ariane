# Ariane

**Ariane is a local command-line orchestrator that turns GitHub issues into reviewed pull requests
with AI coding agents (Claude Code, Codex, opencode, pi), while the human keeps deciding,
understanding and approving.** The name comes from Ariadne's thread (*le fil d'Ariane*): you
never lose the thread of your own code.

What Ariane does with a labelled issue:

- **Runs a coding agent in an isolated git worktree**, with an allow list of environment
  variables (no tracker token, no credentials the project did not declare) and pushing blocked.
- **Replays your checks itself** (lint, types, tests), each in its own clean tree: Ariane never
  takes the agent's word that the tests pass.
- **Has the change reviewed by a different model**: an independent, read-only AI code reviewer
  answers go or no-go against the ticket and your definition of done, with up to two fix rounds.
- **Guards git and your secrets**: a push guard stops the ticket if an agent touches git
  configuration, refs or hooks; everything Ariane posts is redacted.
- **Measures every ticket**: cost, tokens, time, rounds and first-pass verdict, in a journal and
  in `ariane report`; a shadow mode measures Ariane on your project without pushing anything.
- **Delivers one branch and one pull request**, a draft when the reviewer said no-go. You merge.

It runs on Windows, macOS and Linux, from your own machine, with the agent CLIs and logins you
already have. Free software under the AGPL.

**Status:** slice 4 (measurement and shadow mode) is built; its gate is pending the second user's
run on macOS (see [Measure Ariane on your project](#measure-ariane-on-your-project-shadow-mode)).
Slice 3 (review, vendor-neutral) is done: `ariane start <issue>` takes a GitHub issue to a
pull request whose checks Ariane replayed, each in its own clean tree, and that a read-only reviewer on a
different model approved, after up to two fix rounds (`[agents.reviewer]` in `ariane.toml`; the
reviewer can run on Claude Code, opencode, Codex or pi). `ariane verify <branch>` gives a branch finished by
hand the same checks and review. Approvals
(slice 5) come next (see the roadmap in [`docs/spec.md`](docs/spec.md)).

The [benchmark](docs/benchmark.md) compares Ariane with Claude Code used alone on a reference project, with the results so far.

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

Use a fine-grained token limited to the one repository: contents, pull requests and commit statuses: write; issues: read; no workflows, no administration. Ariane removes the token from its own environment once read and keeps it only for the tracker and the push; no other git command gets it, and on Linux its process is not dumpable. The residual: on macOS, on Windows and when running as root, a process of the same user may still read Ariane's memory; only the sandbox of the security slice closes it (ADR 0017).

A check can declare `not_run_locally`, path globs of tests that only CI runs: `checks.md` lists them with the changed files they cover, the implementer is told to write them with extra care, and the reviewer reads those files as untested code (ADR 0042).

A check can also declare `paths`, path globs of the files it covers: when a ticket changes none of them, Ariane skips it, records it as `skipped` in `checks.md`, the pull request body and the reviewer's prompt, and posts a `success` status saying "skipped by Ariane: no changed file matches `paths`". A check without `paths` (or with `always = true`) and the documentation checks always run, and a change to `ariane.toml` or to a file of `project.check_all_paths` (lock files, CI files) runs every check. Every check that runs gets `ARIANE_CHANGED_FILES`, the path of a file listing the changed files one per line, to choose its own tests (ADR 0056).

Each round also has a risk tier, `low` or `high`, computed from its diff and the optional `[checks_policy]` table: `high` when the diff has more than `max_changed_lines` added and removed lines (default 300), touches more than `max_modules` modules (default 3; a module is the first path segment under each `module_roots` folder, by default the repository root), touches a `critical_paths` file, `ariane.toml` or a `check_all_paths` file, or when an earlier round of the ticket failed a check; `low` otherwise. Without the table every round is `high`. Every check gets `ARIANE_RISK_TIER` and `ARIANE_FULL_SUITE`: `1` on a `high` round, or always for a check declaring `full_when = "always"`, else `0`. `checks.md`, the journal, the pull request body and the reviewer's prompt state the tier and its reasons, and a `high` round keeps the full review even when the diff is small enough for `[agents.reviewer.small]`. Ariane never picks tests itself: the check's command decides what a related-tests run is, for example (ADR 0056):

```toml
[checks_policy]
max_changed_lines = 300
module_roots = ["src/*/"]
critical_paths = ["src/auth/**"]

[[checks]]
name = "tests"
command = ["uv", "run", "python", "scripts/tests.py"]
```

```python
# scripts/tests.py: the full suite on a high round, else the tests of the changed files
import os, pathlib, subprocess, sys

args = ["pytest", "-q"]
if os.environ.get("ARIANE_FULL_SUITE", "1") == "0":
    changed = pathlib.Path(os.environ["ARIANE_CHANGED_FILES"]).read_text().splitlines()
    args += [p for p in changed if p.startswith("tests/") and p.endswith(".py")] or ["tests"]
sys.exit(subprocess.call(args))
```

The reviewer is given the ticket's Out of scope section, and a finding about out-of-scope work is never blocking.
The reviewer also checks the order of side effects: a write before the check that should guard it, or a retry that can write twice, is a blocking finding.
The review is in proportion (ADR 0057): a case that neither the ticket nor the specification asks for, and that no acceptance criterion covers, is minor unless it loses data, breaks a security property or makes a check pass wrongly. The residuals the owner accepted in an ADR (an item starting with `- **Accepted residual.**` in `docs/adr/`, read at the base commit) are given to the reviewer, and a finding that is one of them is minor, titled "accepted residual (ADR NNNN)".
With `[review] sensitive_paths` (path globs), a change touching one of those files is pointed out to the reviewer, and its pull request gets the label `owner-review` and a line, above the review, naming the sensitive paths changed; nothing is merged or approved automatically.

The reviewer loads nothing from the tree under review (no hooks, settings or instruction files; ADR 0031): a Claude Code reviewer's `tools` are a subset of `Read`, `Glob`, `Grep`, and it gets the base branch's `CLAUDE.md` in its prompt as data.
The instruction files it could load from outside that tree (`CLAUDE.md` and `CLAUDE.local.md` in the ancestors of its folders, the user-level `CLAUDE.md`, opencode's, Codex's or pi's global instructions and configuration) are guarded from before the first setup command and compared right after every setup (before its check runs), agent session and check: one written by any of them stops the ticket before the review.
A small change can get a lighter review (ADR 0046): with `[agents.reviewer.small]` (`max_lines`, and optional `model`, `max_budget_usd`, `max_tokens`, `timeout_minutes`), a review round whose diff has at most `max_lines` changed lines (added plus deleted, without `work/`, a binary file counting 0) uses those values instead of the reviewer's, and the reviewer is told to review the changed files, their tests and their callers rather than the whole repository. The runtime and tools stay the reviewer's, the small model must still differ from the implementer's, and `ariane verify` applies the same rule; the journal and `metrics.json` (`changed_lines`) record the size. Without the table nothing changes.
The review always gets the full list of changed files (`git diff --name-status`); when the diff is over 200,000 characters it is cut, the prompt names the files whose hunks are missing, and the journal and the pull request body say so.
On Linux, Ariane is the subreaper of the processes it starts: one an agent, a setup or a check leaves running (in its process group or a new session) is killed as soon as that command ends, even when it fails or is interrupted, counted in `metrics.json` and stops the ticket; `ariane verify` keeps the `metrics.json` of a refused run in `<repo>.ariane/verify/<branch>/`.

### Reviewer on Codex

The reviewer can run on the [Codex CLI](https://github.com/openai/codex) (install it and put
`codex` on the PATH): `runtime = "codex"` and `model = "<model>"` in `[agents.reviewer]`. Ariane only drives the official CLI: a read-only `codex exec` with the
prompt on standard input; the read-only sandbox, not `tools`, is what restricts the reviewer (it can
run read-only shell commands, and `tools` has no effect on Codex). Log in once with `codex login` (or `codex login --device-auth`); the
session then bills your ChatGPT plan and `ariane report` shows it as "covered by plan". Keep
`~/.codex/auth.json` private, like a password: Ariane never reads, copies or logs it. Or set
`api_key_env = "<variable>"` in `[agents.reviewer]`: that variable's value is given to the Codex
process only, as `CODEX_API_KEY`, and the session is billed per token. Without `api_key_env`, every
OpenAI key variable is removed from the process's environment. When the plan's usage limit is
reached the ticket stops with "reviewer quota reached", never a no-go: restart it after the reset
time. Not logged in and no `api_key_env`: the ticket stops with "Codex is not logged in". Without
`api_key_env` the CLI must be logged in with ChatGPT: a CLI logged in with an API key stops the
ticket ("Codex is logged in with an API key, not ChatGPT"; run `codex login --device-auth` with the
ChatGPT account, or set `api_key_env`), since `max_tokens` cannot bound a per-token turn (ADR 0043).

### Reviewer on pi

The reviewer can run on the [pi coding agent](https://www.npmjs.com/package/@mariozechner/pi-coding-agent),
which reaches many providers (Anthropic, OpenAI, Google, DeepSeek, OpenRouter, GitHub Copilot and
others). Install it with `npm install -g @mariozechner/pi-coding-agent` and check that `pi --version`
works, then set `runtime = "pi"`, `model = "<provider>/<id>"` (`pi --list-models` lists them),
`tools = ["read", "grep", "find", "ls"]` (or a subset: `bash`, `edit` and `write` are refused) and
`max_tokens` in `[agents.reviewer]`. Ariane only drives the official CLI: `pi -p --mode json` with
the prompt on standard input, the read-only tools, no session file, no extensions, skills, prompt
templates, themes or context files, offline, and `PI_TELEMETRY=0`. Log in once by running `pi` and
`/login` (an API key, or a subscription such as ChatGPT Plus/Pro, Claude Pro/Max or GitHub Copilot):
pi stores it in `~/.pi/agent/auth.json` (or under `PI_CODING_AGENT_DIR`). Keep that file private,
like a password: Ariane never reads, copies or logs it, and gives the process no provider key from
its own environment. Or set `api_key_env = "<variable>"` in `[agents.reviewer]`: that variable's
value is given to the pi process only, under the provider's own variable (`ANTHROPIC_API_KEY` for
`anthropic/...`). `max_tokens` is required because pi may bill per token whatever the login (pi's
docs say Claude Pro/Max through pi draws from extra usage); `max_budget_usd` stops the session on the cost pi reports, and `ariane report` shows it.
Without credentials the ticket stops with "pi has no credentials for <provider>", never a no-go. A
`.pi/` folder in the repository is left out of the reviewer's tree, and pi's `settings.json`,
`models.json`, `AGENTS.md`, `SYSTEM.md` and `APPEND_SYSTEM.md` are guarded (ADR 0051).

### Reviewer on opencode

The reviewer can run on [opencode](https://opencode.ai) (install it separately and put `opencode`
on the PATH) with another vendor's model: set `runtime = "opencode"`, `model = "<provider>/<model>"`
and `tools = ["read", "glob", "grep"]` in `[agents.reviewer]`, and export the provider's key (for
example `OPENAI_API_KEY`). The implementer stays on Claude Code. `ARIANE_CONFIG` names a
configuration file to read instead of `ariane.toml` for one run (it does not reach the agents or
the checks);
[`docs/ariane.opencode-reviewer.example.toml`](docs/ariane.opencode-reviewer.example.toml) is Ariane's
own configuration with the reviewer on opencode (ADR 0029). Its `max_tokens` is large (1,500,000)
because opencode reports cache reads again at every step and Ariane counts them, so a normal review
counts over a million tokens; a reviewer stopped at a cap names the key to raise
(`agents.reviewer.max_tokens` or `agents.reviewer.max_budget_usd`).

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
otherwise it exits 2 before creating anything. Ariane waits up to 15 seconds for GitHub to list
the label event when it lags behind the issue. Add the label to each ticket you want to run, and
add it again after any later change, comments and the pull request's own reference included (for
example before `ariane verify --issue N`) ([ADR 0032](docs/adr/0032-issue-gate.md)).

`ariane start` creates the branch `ariane/12` in a working tree beside the repository
(`<repo>.ariane/worktrees/12`), runs the setup command, one implementer session and every check. If a blocking check fails
before any review, it stops there and pushes nothing. Otherwise a read-only reviewer on a
different model reviews the delivered commit; on a no-go, up to two fix rounds follow, each with a fresh
implementer session, a replay and a review (a fix round that changes nothing ends the rounds, with a draft pull request). Then it pushes the branch, opens the pull request (a
draft that needs a human if the review is still no-go) and publishes each check's result as a
commit status (`ariane/<check name>`) on its head commit. The ticket's records are in `work/12/`; the
last of them (the status `delivered` with the pull request, and the journal's push and pull request
entries) is committed on the local branch only, after the push, so the ticket's working tree is
clean and the next push of the branch carries it. They include `work/12/metrics.json`: cost, tokens, durations,
fix rounds, first-pass verdict and outcome of the ticket, rewritten after each step.
Each agent session stops at its limits, set per role in `[agents.<role>]`: its cost
(`max_budget_usd`), its tokens (`max_tokens`), its total time (`timeout_minutes`) and its idle time
(`idle_minutes`, 10 by default): a session that sends no event for that long is stopped as a
`timeout`, and the journal and the stop line say "no activity for <m> min (idle limit)" with the
last event ([ADR 0045](docs/adr/0045-idle-limit-of-agent-sessions.md)). Its work is kept on the
branch.

**Restarting a stopped ticket.** A ticket that stopped (a blocking check, a budget stop, a
reviewer failure) or whose process died (Ctrl-C, a machine restart) leaves its working trees and
its branch, so `ariane start 12` refuses it and names `--restart`. `ariane start 12 --restart`
removes the ticket's working trees (`12`, `12-review`, `12-replay-*`), keeps the branch
`ariane/12` as `ariane-restarted/12-<UTC time>` (kept, never deleted: what the previous run
committed stays there) and starts the ticket as a new run, whose journal opens with what was
removed and kept. Files the previous run left uncommitted in its working tree `12`, modified or
untracked (not ignored), and staged content, are first saved in commits on top of the kept
branch, written before any tree is removed. It refuses while
another `ariane start 12` runs (each run holds `<repo>.ariane/locks/12.lock`), when `ariane/12` is
already on the remote, and with `--shadow` (remove the clone instead). `ariane report` counts the
time from the previous stop to the restart in the human time
([ADR 0047](docs/adr/0047-restart-a-stopped-ticket.md)).

PowerShell:

```powershell
ariane start 12 --restart
if ($LASTEXITCODE -ne 0) { ariane status 12 }
```

bash:

```bash
ariane start 12 --restart || ariane status 12
```

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
replay of the checks (each in its own tree), one review, then `work/verify/<branch>/review.md`, `checks.md` and `metrics.json` committed
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

## Measure Ariane on your project (shadow mode)

This is the path for a second user on macOS (it works the same on Linux and Windows) who wants to
know whether Ariane does at least as well as their current process, on their own project.

**Prerequisites:** [uv](https://docs.astral.sh/uv/), git, Claude Code (`claude`) logged in, and a
GitHub token with read access to the project's issues.

1. **Install Ariane** ([ADR 0021](docs/adr/0021-second-user-distribution-and-contributions.md)).
2. **Configure it.** Download [`docs/ariane.example.toml`](docs/ariane.example.toml) from Ariane's
   repository to the root of your repository as `ariane.toml` (commands below) and set
   `repository`, the checks and the agents.
3. **Label each ticket** `ariane`, by a person with write access, and again after any later edit or
   comment; otherwise `ariane start` refuses the ticket and exits 2 (see above, ADR 0032).
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

Shadow mode never pushes, opens a pull request, sets a
status, posts a comment or writes to your repository: it works in a separate clone.

**Pass criteria over 10 tickets:** no agent push or pull-request attempt, no write to real data, no
guard violation, Ariane's diff judged acceptable by you in at least 8, cost and duration recorded.
`ariane report` prints `shadow pass: yes|no` over the last 10 tickets (no attempt, no violation,
at least 8 accepted); cost, duration and real data are for you to check.

**Keep a short log of your current process** for the same tickets (your minutes per merged pull
request, and the steps skipped or gates bypassed). The comparison is on two numbers: human time per
merged pull request and the count of steps skipped or gates bypassed; Ariane's come from
`ariane report`, and the owner decides on them (spec, "Measuring Ariane").

## While a ticket runs

The project's setup, checks and agents receive an allow list of environment variables (ADR 0024):
system variables (`PATH`, `HOME`, `USER`, `LANG`, `LC_*`, `TZ`, `TERM`, the temporary folders, and
the Windows system variables), proxy and certificate settings (`HTTP_PROXY`, `HTTPS_PROXY`,
`NO_PROXY`, `ALL_PROXY`, `SSL_CERT_FILE`, `REQUESTS_CA_BUNDLE`, ...), and, for agents, the login
variables of their runtime. A proxy URL with credentials (`http://user:pass@host`) is left out
unless declared. Any other variable reaches them only when the project declares it in
`ariane.toml`:

```toml
[project]
env = ["DATABASE_URL", "MYAPP_"]  # an entry ending in "_" is a prefix
```

A declared name that looks like a secret still passes, and the ticket's journal names it (never its
value); its value is masked in what Ariane writes. The tracker token, any `ARIANE_*` variable and
Ariane's own virtual environment (`VIRTUAL_ENV` and its scripts directory on `PATH`) never pass,
even if declared.

### `ARIANE_SLOT`: keep local resources apart

Each `ariane start` (shadow included) and `ariane verify` holds a slot, a number from 0 to 15 that
no other Ariane run on the machine holds at the same time (a file lock in `~/.ariane/slots/`,
released when the run ends or its process dies; ADR 0050). The setup, every check, every agent
session and the commit hooks get it as `ARIANE_SLOT`. Ariane does not know your project's ports:
derive them, or anything else two runs must not share, from it. With all 16 slots held, a run
refuses to start ("16 Ariane runs already hold a slot on this machine. Next: wait for one to
end."). For example, a check script that starts the project's local stack on a base port plus
the slot:

```powershell
$slot = if ($env:ARIANE_SLOT) { [int]$env:ARIANE_SLOT } else { 0 }
$port = 8000 + $slot
```

```bash
port=$((8000 + ${ARIANE_SLOT:-0}))
```

**Parallel checks.** Each check is replayed in its own clean tree (setup, then that check), one
after another by default. `project.parallel_checks = 3` replays up to three checks at the same
time, as CI jobs do, for `ariane start` and `ariane verify` alike; the report and the statuses
keep the declared order. Each check running at once has its own slot, so its `ARIANE_SLOT`
differs from the others': the run's own slot, then the next free ones. When fewer slots are free,
fewer checks run at once and the journal says how many (`ticket.checks.parallel`). A stop
(a failing setup, Ctrl-C, a guard violation) kills the other checks and removes every tree
([ADR 0052](docs/adr/0052-parallel-checks.md)). Declare it only for checks that do not depend on
each other.

**Dependency caches.** A fresh tree per check means installing the dependencies in every tree of
every round. A `[[project.cache]]` table names a folder (`path`, such as `node_modules` or
`.venv`, ignored by git), the files whose content identifies it (`key`, such as the lock file)
and the command that builds that folder alone (`setup`):

```toml
[[project.cache]]
path = "worker/node_modules"
key = ["worker/package-lock.json"]
setup = ["npm", "ci", "--prefix", "worker"]
```

The first replay tree with a given key (the SHA-256 of the key files and of `setup`) runs that
`setup` and stores the folder, read-only, in `<repo>.ariane/cache/<key>/`; the next trees copy it
(copy-on-write where the file system can, never hard links, so a write into a tree's copy leaves
the store unchanged) instead of running `setup`. `project.setup` (or a check's own `setup`) then
runs as before, for the rest. Only Ariane's replay trees fill the store; the ticket's own tree,
where the agent works, copies a stored folder or builds its own, never stores it. An entry not
completely written is never used: it is built again. A cache path that the commit already has, or that
goes through a symbolic link, is never written from the store: its `setup` runs as without a
cache. The journal lists, per check, which caches
were copied and which built (`ticket.checks.cache`). At the start of a ticket only the `keep`
(default 5) most recently used entries of each path are kept. For a uv project, cache
the dependencies (`setup = ["uv", "sync", "--frozen", "--no-install-project"]`, key `uv.lock`),
let `project.setup` install the project itself, and run tools as `uv run python -m <tool>`,
since a virtual environment's scripts name the tree that built them
([ADR 0054](docs/adr/0054-dependency-cache.md); examples in
[`docs/ariane.example.toml`](docs/ariane.example.toml)).

Only Ariane runs git commands in the repository while a ticket runs. Several tickets may run at
once on one repository (one `ariane start` each): each run is registered in
`<repo>.ariane/runs/<n>` while it lasts. Ariane checks that the agent changed nothing outside the
ticket branch (git configuration, hooks, local branches, the remote); the only change it
tolerates is another registered run's own bookkeeping: its branch `ariane/<m>` and that
branch's `remote` and `merge` keys, and only for a run Ariane saw running. Anything else, even another key of that branch, stops the
ticket. A merge on the base branch (a fast-forward) does not stop the ticket; any other remote
change does: a created, deleted or rewritten branch or tag, a base branch that did not
fast-forward, or any change to the ticket's branch. The stop line names the refs (ADR 0017).
Another run's fetch of a base branch that advanced by a merge does not stop the ticket either:
the base's tracking ref may fast-forward to the commit the remote's base points to, and the
ticket keeps the base it started from; any other move of that ref stops it (ADR 0055).

Only Ariane pushes, with the tracker token sent as an HTTP authorization header for that one push
(the machine's credential helpers are off). Without a token, or if that push is refused for
authentication, Ariane pushes once more without the header and journals which way it went.

In a cloud sandbox whose proxy supplies its own credentials, an agent's push is detected after
the session, not prevented (ADR 0017). To check what your proxy does, run `git push --dry-run`
or a push of a throwaway branch from a session without the token and see whether it is accepted.

## Develop Ariane

From a clone, `uv sync` installs the development tools; the checks are listed in
[`CLAUDE.md`](CLAUDE.md) ("Checks"). `uv run pytest` runs the tests in parallel, one worker per
CPU (`pytest-xdist`, `-n auto`); `uv run pytest -n 0` runs them serially, for example to debug
one test with `pdb`. CI runs the checks with Python 3.13 on Windows, macOS and Linux, and with
Python 3.11, the minimum, on Linux only ([ADR 0048](docs/adr/0048-parallel-tests-and-ci-matrix.md)).
The tests' git project is built once per worker and copied for each test
([ADR 0049](docs/adr/0049-template-project-and-windows-shards.md)). Windows CI runs the tests in
two shards, `uv run pytest --splits 2 --group 1` (or `2`) with `--splitting-algorithm
least_duration`, balanced from `.test_durations` (refresh it with `uv run pytest
--store-durations`); every other CI job runs the whole suite.

## License

Ariane is free software under the [GNU Affero General Public License v3.0 only](LICENSE)
(`AGPL-3.0-only`): you may use, study, modify and share it, and anyone who offers a modified
Ariane to others, including as a network service, must publish their changes under the same
license. Other licensing terms can be arranged with the copyright holder
([ADR 0008](docs/adr/0008-license.md), [ADR 0021](docs/adr/0021-second-user-distribution-and-contributions.md)).
Fixes are sent as issues.
