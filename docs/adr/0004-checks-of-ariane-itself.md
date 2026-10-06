# 0004. Checks of Ariane itself

- Status: accepted
- Date: 2026-10-06
- Capabilities: C9 (for Ariane's own code), maintainability requirement

## Context
CLAUDE.md rule 6 asks slice 1 to choose the lint, type and test commands, and the
maintainability requirement asks for a file-length limit (600 lines) checked from slice 1.

## Decision
The checks, run from the repository root after `uv sync`:

| Check | Command |
| --- | --- |
| Lint | `uv run ruff check .` |
| Format | `uv run ruff format --check .` |
| Types | `uv run mypy` (strict mode, configured in `pyproject.toml`) |
| Tests | `uv run pytest` |
| File length | `uv run python scripts/check_file_length.py` (no file over 600 lines under `src/`, `tests/`, `scripts/`) |

The same list is written in CLAUDE.md under "Checks", declared in Ariane's own `ariane.toml`,
and run by CI.

The file-length limit applies to Ariane's own source, not to generated files (`uv.lock`) or
ticket records (`work/`), which can be long by nature.

## Consequences
One tool (ruff) for lint and format, one for types. mypy is pure Python, so it needs no Node
runtime on contributors' machines.

## Alternatives considered
- pyright: fast, but needs Node.js.
- flake8 + black + isort: three tools where ruff is one.
- unittest: no dependency, but pytest's fixtures (`tmp_path`, `monkeypatch`) make the
  subprocess and git tests far shorter.
