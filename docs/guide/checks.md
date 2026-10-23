# Checks: how Ariane replays them

Ariane never takes an agent's word that the tests pass: it runs the checks of `ariane.toml`
itself, each in its own clean working tree at the delivered commit, after the setup command, and
publishes each result as a commit status `ariane/<check name>` (C9). This page covers what a check
can declare and how the replay runs. The full list of keys is in the
[JSON Schema of `ariane.toml`](../reference/ariane.toml.schema.json) and in
[`ariane.example.toml`](../ariane.example.toml).

## What a check can declare

**`not_run_locally`**: path globs of tests that only CI runs. `checks.md` lists them with the
changed files they cover, the implementer is told to write them with extra care, and the reviewer
reads those files as untested code (ADR 0042).

**`paths`**: path globs of the files the check covers. When a ticket changes none of them, Ariane
skips the check, records it as `skipped` in `checks.md`, the pull request body and the reviewer's
prompt, and posts a `success` status saying "skipped by Ariane: no changed file matches `paths`".
A check without `paths` (or with `always = true`) and the documentation checks always run, and a
change to `ariane.toml` or to a file of `project.check_all_paths` (lock files, CI files) runs
every check. Every check that runs gets `ARIANE_CHANGED_FILES`, the path of a file listing the
changed files one per line, to choose its own tests (ADR 0056).

## Risk tier and related tests

Each round has a risk tier, `low` or `high`, computed from its diff and the optional
`[checks_policy]` table: `high` when the diff has more than `max_changed_lines` added and removed
lines (default 300), touches more than `max_modules` modules (default 3; a module is the first path
segment under each `module_roots` folder, by default the repository root), touches a
`critical_paths` file, `ariane.toml` or a `check_all_paths` file, or when an earlier round of the
ticket failed a check; `low` otherwise. Without the table every round is `high`.

Every check gets `ARIANE_RISK_TIER` and `ARIANE_FULL_SUITE`: `1` on a `high` round, or always for a
check declaring `full_when = "always"`, else `0`. `checks.md`, the journal, the pull request body
and the reviewer's prompt state the tier and its reasons, and a `high` round keeps the full review
even when the diff is small enough for `[agents.reviewer.small]`. Ariane never picks tests itself:
the check's command decides what a related-tests run is, for example (ADR 0056):

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

## Full replay: measuring what selection misses

When the last round of a ticket skipped a check or ran one with `ARIANE_FULL_SUITE=0`, a sample of
the tickets (`[checks_policy] full_replay_sample`, default 0.2, drawn from the ticket number and the
commit so a rerun gives the same choice; 0 disables it) get a full replay after the delivery: every
check, `ARIANE_FULL_SUITE=1`, in fresh replay trees of the same commit. It never delays or changes
the push, the pull request or the review.

A check that fails only there is an escape: `work/<n>/full-replay.md` records it with its output,
the journal logs `ticket.checks.escape`, a comment on the pull request names the check, and the
`ariane/full-replay` status fails; a passing full replay posts a success. A check that fails before
a later one stops the full replay is still an escape. `full-replay` is reserved: no check may take
that name. The defaults apply without the table too. `ariane report` gives the escape rate and
warns above `[checks_policy] max_escape_rate` (default 0.02); turning selection off stays the
owner's call.

## Parallel checks

Each check is replayed in its own clean tree (setup, then that check), one after another by
default. `project.parallel_checks = 3` replays up to three checks at the same time, as CI jobs do,
for `ariane start` and `ariane verify` alike; the report and the statuses keep the declared order.
Each check running at once has its own slot (see below), so its `ARIANE_SLOT` differs from the
others': the run's own slot, then the next free ones. When fewer slots are free, fewer checks run
at once and the journal says how many (`ticket.checks.parallel`). A stop (a failing setup, Ctrl-C,
a guard violation) kills the other checks and removes every tree
([ADR 0052](../adr/0052-parallel-checks.md)). Declare it only for checks that do not depend on
each other.

## Dependency caches

A fresh tree per check means installing the dependencies in every tree of every round. A
`[[project.cache]]` table names a folder (`path`, such as `node_modules` or `.venv`, ignored by
git), the files whose content identifies it (`key`, such as the lock file) and the command that
builds that folder alone (`setup`):

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
completely written is never used: it is built again. A cache path that the commit already has, or
that goes through a symbolic link, is never written from the store: its `setup` runs as without a
cache. The journal lists, per check, which caches were copied and which built
(`ticket.checks.cache`). At the start of a ticket only the `keep` (default 5) most recently used
entries of each path are kept.

For a uv project, cache the dependencies (`setup = ["uv", "sync", "--frozen",
"--no-install-project"]`, key `uv.lock`), let `project.setup` install the project itself, and run
tools as `uv run python -m <tool>`, since a virtual environment's scripts name the tree that built
them ([ADR 0054](../adr/0054-dependency-cache.md); examples in
[`ariane.example.toml`](../ariane.example.toml)).

## `ARIANE_SLOT`: keep local resources apart

Each `ariane start` (shadow included), `ariane update` and `ariane verify` holds a slot, a number
from 0 to 15 that no other Ariane run on the machine holds at the same time (a file lock in
`~/.ariane/slots/`, released when the run ends or its process dies; ADR 0050). The setup, every
check and every agent session get it as `ARIANE_SLOT`. Git hooks never run in Ariane's own git
commands (they could be code an agent planted), so no commit hook receives it. Ariane does not
know your project's ports: derive them, or anything else two runs must not share, from the slot.
With all 16 slots held, a run refuses to start ("16 Ariane runs already hold a slot on this
machine. Next: wait for one to end."). For example, a check script that starts the project's
local stack on a base port plus the slot:

```powershell
$slot = if ($env:ARIANE_SLOT) { [int]$env:ARIANE_SLOT } else { 0 }
$port = 8000 + $slot
```

```bash
port=$((8000 + ${ARIANE_SLOT:-0}))
```

## The environment the project receives

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

A declared name that looks like a secret still passes, and the ticket's journal names it (never
its value); its value is masked in what Ariane writes. The tracker token, any `ARIANE_*` variable
and Ariane's own virtual environment (`VIRTUAL_ENV` and its scripts directory on `PATH`) never
pass, even if declared.

## Statuses published from CI

Ariane's own repository has a GitHub Actions workflow, `.github/workflows/check-statuses.yml`, that
replays the declared checks on the head of an `ariane/<n>` pull request and publishes one status
per check, for when Ariane cannot publish them itself (for example from a cloud session without
the token). The statuses come from running the checks in the workflow, never from a report file of
the branch ([ADR 0018](../adr/0018-clean-tree-replay-and-statuses.md)). The workflow and its
script are specific to Ariane's repository: another project does not need them, since Ariane
publishes the statuses itself when it pushes.
