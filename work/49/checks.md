# Checks

Replayed by Ariane on commit `825cec9dbc041f6f9fe4f857381bb9557207604d`.

| Check | Blocking | Result | Duration |
| --- | --- | --- | --- |
| lint | yes | pass | 0.2 s |
| format | yes | pass | 0.1 s |
| types | yes | pass | 3.4 s |
| tests | yes | pass | 58.7 s |
| file length | yes | pass | 0.1 s |

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
137 files already formatted
```

## types

- Command: `uv run mypy`
- Blocking: yes
- Result: passed (exit 0, 3.4 s)

```text
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
warning: `VIRTUAL_ENV=/home/user/ariane/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Success: no issues found in 36 source files
```

## tests

- Command: `uv run pytest -q`
- Blocking: yes
- Result: passed (exit 0, 58.7 s)

```text
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
warning: `VIRTUAL_ENV=/home/user/ariane/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
........................................................................ [ 36%]
........................................................................ [ 73%]
...............s.....................................                    [100%]
196 passed, 1 skipped in 57.94s
```

## file length

- Command: `uv run python scripts/check_file_length.py`
- Blocking: yes
- Result: passed (exit 0, 0.1 s)

```text
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
warning: `VIRTUAL_ENV=/home/user/ariane/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
file length OK: no file over 600 lines under src, tests, scripts
```

Summary: 5 passed, 0 failed (0 blocking).
