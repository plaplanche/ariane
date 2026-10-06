# 0001. Package layout and toolchain

- Status: accepted
- Date: 2026-10-06
- Capabilities: C22, C23 (platform and dependency requirements)

## Context
Slice 1 needs a Python package that installs and runs the same way on Windows (PowerShell 5.1
and 7), macOS and Linux, including cloud sandboxes running as root behind an HTTPS proxy. The
spec asks for as few dependencies as possible, each justified in an ADR.

## Decision
- `src/` layout: the package lives in `src/ariane/`, tests in `tests/`.
- Python 3.11 or later (`tomllib` is in the standard library from 3.11).
- No runtime dependency in slice 1: `argparse`, `tomllib`, `subprocess`, `urllib.request` and
  `json` cover the CLI, the configuration, processes and the GitHub REST API.
- Build backend `hatchling` (build-time only). Development dependencies (`pytest`, `ruff`,
  `mypy`) are declared in a `dev` dependency group.
- `uv` manages the environment and the lock file `uv.lock`, which is committed. A contributor
  runs `uv sync` once, then every check through `uv run`.
- The console entry point is `ariane = "ariane.cli:main"`; `python -m ariane` works too.

## Consequences
Installing Ariane pulls nothing beyond Python. HTTP, argument parsing and validation are written
by hand, which costs some code but keeps the surface small. Contributors need `uv`.

## Alternatives considered
- Flat layout: lets tests import the working copy instead of the installed package by accident.
- `requests`/`httpx`, `click`/`typer`, `pydantic`: convenient but each is a dependency the
  standard library already covers for slice 1's needs.
- Poetry or plain pip + venv: uv is faster, locks across platforms and installs Python itself.
