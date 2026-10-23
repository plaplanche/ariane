# Reviewers: what the review checks and where it runs

After the checks pass, a read-only reviewer on a different model reads the delivered commit and
answers `go` or `no-go`, with blocking and minor findings, against the ticket and the definition
of done, item by item (C10). On a `no-go`, up to two fix rounds follow. The implementer always runs
on Claude Code; the reviewer can run on Claude Code, Codex, pi or opencode, configured in
`[agents.reviewer]` of `ariane.toml`. The configuration refuses a reviewer whose model is the
implementer's.

## What the reviewer is told

- The ticket's Out of scope section: a finding about out-of-scope work is never blocking.
- The order of side effects: a write before the check that should guard it, or a retry that can
  write twice, is a blocking finding.
- The review is in proportion (ADR 0057): a case that neither the ticket nor the specification
  asks for, and that no acceptance criterion covers, is minor unless it loses data, breaks a
  security property or makes a check pass wrongly.
- The residuals the owner accepted in an ADR (only those written as an item starting with `- **Accepted residual.**` in
  `docs/adr/`, read at the base commit): a finding that is one of them is minor, titled "accepted
  residual (ADR NNNN)".
- With `[review] sensitive_paths` (path globs), a change touching one of those files is pointed
  out to the reviewer, and its pull request gets the label `owner-review` and a line, above the
  review, naming the sensitive paths changed; nothing is merged or approved automatically.
- The full list of changed files (`git diff --name-status`); when the diff is over 200,000
  characters it is cut, the prompt names the files whose hunks are missing, and the journal and
  the pull request body say so.
- From the second round on, the earlier rounds' blocking findings: the fix session sees them too,
  and the reviewer says, for each, whether it is fixed, still open or replaced by a finding its fix
  caused. When the last review still has such a recurring finding, the draft pull request says that
  the rounds circled on the same design question and lists the chain of findings, and
  `ariane report` shows `recurring_findings` (ADR 0059).

## Isolation

The reviewer loads nothing from the tree under review (no hooks, settings or instruction files;
[ADR 0031](../adr/0031-reviewer-isolation.md)): it reads a separate tree without `CLAUDE.md`,
`AGENTS.md`, `.claude/`, `.codex/` or `.pi/`; a Claude Code reviewer's `tools` are a subset of
`Read`, `Glob`, `Grep`, and it gets the base branch's `CLAUDE.md` in its prompt as data.

The instruction files it could load from outside that tree (`CLAUDE.md` and `CLAUDE.local.md` in
the ancestors of its folders, the user-level `CLAUDE.md`, opencode's, Codex's or pi's global
instructions and configuration) are guarded from before the first setup command and compared right
after every setup (before its check runs), agent session and check: one written by any of them
stops the ticket before the review. A user-level `CLAUDE.md` that existed before the ticket is
still loaded by a Claude Code reviewer (an accepted residual of ADR 0031).

## A lighter review for a small change

With `[agents.reviewer.small]` (`max_lines`, and optional `model`, `max_budget_usd`, `max_tokens`,
`timeout_minutes`), a review round whose diff has at most `max_lines` changed lines (added plus
deleted, without `work/`, a binary file counting 0) uses those values instead of the reviewer's,
and the reviewer is told to review the changed files, their tests and their callers rather than
the whole repository (ADR 0046). The runtime and tools stay the reviewer's, the small model must
still differ from the implementer's, and `ariane verify` applies the same rule; the journal and
`metrics.json` (`changed_lines`) record the size. A `high` risk round keeps the full review (see
[checks](checks.md#risk-tier-and-related-tests)). Without the table nothing changes.

## Reviewer on Codex

The reviewer can run on the [Codex CLI](https://github.com/openai/codex) (install it and put
`codex` on the PATH): `runtime = "codex"` and `model = "<model>"` in `[agents.reviewer]`. Ariane
only drives the official CLI: a read-only `codex exec` with the prompt on standard input; the
read-only sandbox, not `tools`, is what restricts the reviewer (it can run read-only shell
commands, and `tools` has no effect on Codex).

Log in once with `codex login` (or `codex login --device-auth`); the session then bills your
ChatGPT plan and `ariane report` shows it as "covered by plan". Keep `~/.codex/auth.json` private,
like a password: Ariane never reads, copies or logs it. Or set `api_key_env = "<variable>"` in
`[agents.reviewer]`: that variable's value is given to the Codex process only, as
`CODEX_API_KEY`, and the session is billed per token. Without `api_key_env`, every OpenAI key
variable is removed from the process's environment.

When the plan's usage limit is reached the ticket stops with "reviewer quota reached", never a
no-go: restart it after the reset time. Not logged in and no `api_key_env`: the ticket stops with
"Codex is not logged in". Without `api_key_env` the CLI must be logged in with ChatGPT: a CLI
logged in with an API key stops the ticket ("Codex is logged in with an API key, not ChatGPT"; run
`codex login --device-auth` with the ChatGPT account, or set `api_key_env`), since `max_tokens`
cannot bound a per-token turn (ADR 0043).

## Reviewer on pi

The reviewer can run on the
[pi coding agent](https://www.npmjs.com/package/@mariozechner/pi-coding-agent), which reaches many
model providers. Install it with `npm install -g @mariozechner/pi-coding-agent` and check that
`pi --version` works, then set `runtime = "pi"`, `model = "<provider>/<id>"` (`pi --list-models`
lists them), `tools = ["read", "grep", "find", "ls"]` (or a subset: `bash`, `edit` and `write` are
refused) and `max_tokens` in `[agents.reviewer]`. Ariane only drives the official CLI:
`pi -p --mode json` with the prompt on standard input, the read-only tools, no session file, no
extensions, skills, prompt templates, themes or context files, offline, and `PI_TELEMETRY=0`.

Log in once by running `pi` and `/login` (an API key or a subscription): pi stores it in
`~/.pi/agent/auth.json` (or under `PI_CODING_AGENT_DIR`). Keep that file private, like a password:
Ariane never reads, copies or logs it, and gives the process no provider key from its own
environment. Or set `api_key_env = "<variable>"` in `[agents.reviewer]`: that variable's value is
given to the pi process only, under the provider's own variable (`ANTHROPIC_API_KEY` for
`anthropic/...`). `max_tokens` is required because pi may bill per token whatever the login (pi's docs say a
Claude subscription used through pi draws from extra usage);
`max_budget_usd` stops the session on the cost pi reports, and `ariane report` shows it. Without
credentials the ticket stops with "pi has no credentials for <provider>", never a no-go. A `.pi/`
folder in the repository is left out of the reviewer's tree, and pi's `settings.json`,
`models.json`, `AGENTS.md`, `SYSTEM.md` and `APPEND_SYSTEM.md` are guarded (ADR 0051).

## Reviewer on opencode

The reviewer can run on [opencode](https://opencode.ai) (install it separately and put `opencode`
on the PATH) with another vendor's model: set `runtime = "opencode"`,
`model = "<provider>/<model>"` and `tools = ["read", "glob", "grep"]` in `[agents.reviewer]`, and
export the provider's key (for example `OPENAI_API_KEY`).
[`ariane.opencode-reviewer.example.toml`](../ariane.opencode-reviewer.example.toml) is Ariane's own
configuration with the reviewer on opencode (ADR 0029). Its `max_tokens` is large (1,500,000)
because opencode reports cache reads again at every step and Ariane counts them, so a normal review
counts over a million tokens; a reviewer stopped at a cap names the key to raise
(`agents.reviewer.max_tokens` or `agents.reviewer.max_budget_usd`).

`ARIANE_CONFIG` names a configuration file to read instead of `ariane.toml` for one run (it does
not reach the agents or the checks):

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
