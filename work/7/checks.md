# Checks

Replayed by Ariane on commit `d48f1f9e6ebc18ee2afb411a2e3eeb5f8b89383c`.

| Check | Blocking | Result | Duration |
| --- | --- | --- | --- |
| lint | yes | pass | 0.3 s |
| format | yes | pass | 0.3 s |
| types | yes | pass | 1.0 s |
| tests | yes | pass | 419.6 s |
| file length | yes | pass | 0.4 s |

## lint

- Command: `uv run ruff check .`
- Blocking: yes
- Result: passed (exit 0, 0.3 s)

```text
warning: `VIRTUAL_ENV=C:\Users\phili\dev\ariane\.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
All checks passed!
```

## format

- Command: `uv run ruff format --check .`
- Blocking: yes
- Result: passed (exit 0, 0.3 s)

```text
warning: `VIRTUAL_ENV=C:\Users\phili\dev\ariane\.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
46 files already formatted
```

## types

- Command: `uv run mypy`
- Blocking: yes
- Result: passed (exit 0, 1.0 s)

```text
warning: `VIRTUAL_ENV=C:\Users\phili\dev\ariane\.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Success: no issues found in 27 source files
```

## tests

- Command: `uv run pytest -q`
- Blocking: yes
- Result: passed (exit 0, 419.6 s)

```text
warning: `VIRTUAL_ENV=C:\Users\phili\dev\ariane\.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
........................................................................ [ 61%]
.................s.........................s..                           [100%]
116 passed, 2 skipped in 418.70s (0:06:58)
```

## file length

- Command: `uv run python scripts/check_file_length.py`
- Blocking: yes
- Result: passed (exit 0, 0.4 s)

```text
warning: `VIRTUAL_ENV=C:\Users\phili\dev\ariane\.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
file length OK: no file over 600 lines under src, tests, scripts
```

Summary: 5 passed, 0 failed (0 blocking).
