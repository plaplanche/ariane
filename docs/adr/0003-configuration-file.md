# 0003. Configuration file

- Status: accepted
- Date: 2026-10-06
- Capabilities: C22, C8, C9, C5, C1

## Context
C22 asks for one configuration file in the repository, refused at start-up with a message naming
the faulty key. Ariane works for any language, so the file cannot be tied to Python tooling.

## Decision
- File `ariane.toml` at the repository root, read with `tomllib`.
- Every command is an argument list, never a shell string (non-functional requirement
  "Processes").
- Slice 1 keys (everything else is refused as unknown):

```toml
[project]
base_branch = "main"
setup = ["uv", "sync"]             # optional (C8)

[tracker]
kind = "github"                    # only value in slice 1
repository = "owner/name"
token_env = "GH_TOKEN"             # name of the variable holding the token, never the token
api_url = "https://api.github.com" # optional, default shown

[agents.implementer]
runtime = "claude-code"            # only value in slice 1
model = "<model id>"
tools = ["Read", "Edit", "Write", "Glob", "Grep", "Bash"]
max_budget_usd = 5.0
timeout_minutes = 30

[[checks]]
name = "tests"
command = ["uv", "run", "pytest"]
blocking = true                    # default true
timeout_minutes = 15               # default 15
```

- Validation is hand-written: wrong type, missing required key, unknown key and bad value each
  produce `ariane.toml: <dotted.key>: <problem>` and exit code 2, before any other work.

## Consequences
Language-neutral, readable on every platform, no dependency. Later slices add keys (rules,
sensitive paths, budgets per ticket) by extending the validator.

## Alternatives considered
- `[tool.ariane]` in `pyproject.toml`: ties a language-neutral tool to Python projects.
- YAML: needs a dependency and has surprising typing rules.
- JSON: no comments.
