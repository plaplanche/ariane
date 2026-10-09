# Checks

Replayed by Ariane on commit `5039f41af5047b6df4c722f85dcf82b179180190`.

| Check | Blocking | Result | Duration |
| --- | --- | --- | --- |
| lint | yes | pass | 0.2 s |
| format | yes | pass | 0.1 s |
| types | yes | pass | 3.3 s |
| tests | yes | pass | 50.2 s |
| file length | yes | pass | 0.2 s |

## lint

- Command: `uv run ruff check .`
- Blocking: yes
- Result: passed (exit 0, 0.2 s)

```text
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
warning: `VIRTUAL_ENV=/home/user/ariane/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
All checks passed!
```

## format

- Command: `uv run ruff format --check .`
- Blocking: yes
- Result: passed (exit 0, 0.1 s)

```text
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
warning: `VIRTUAL_ENV=/home/user/ariane/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
115 files already formatted
```

## types

- Command: `uv run mypy`
- Blocking: yes
- Result: passed (exit 0, 3.3 s)

```text
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
warning: `VIRTUAL_ENV=/home/user/ariane/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Success: no issues found in 34 source files
```

## tests

- Command: `uv run pytest -q`
- Blocking: yes
- Result: passed (exit 0, 50.2 s)

```text
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
warning: `VIRTUAL_ENV=/home/user/ariane/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
........................................................................ [ 41%]
........................................................................ [ 83%]
..s..........................                                            [100%]
172 passed, 1 skipped in 49.43s
```

## file length

- Command: `uv run python scripts/check_file_length.py`
- Blocking: yes
- Result: passed (exit 0, 0.2 s)

```text
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
warning: `VIRTUAL_ENV=/home/user/ariane/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
file length OK: no file over 600 lines under src, tests, scripts
```

Summary: 5 passed, 0 failed (0 blocking).
