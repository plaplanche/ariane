# Checks

Replayed by Ariane on commit `5ca5841d27a308116ac74a6aa6346b20334d51f7`.

Each check was replayed in its own clean working tree at `5ca5841d27a308116ac74a6aa6346b20334d51f7`, after the setup.

| Check | Blocking | Result | Duration |
| --- | --- | --- | --- |
| lint | yes | pass | 0.1 s |
| format | yes | pass | 0.1 s |
| types | yes | pass | 2.9 s |
| tests | yes | pass | 111.0 s |
| file length | yes | pass | 0.1 s |
| docs: references | yes | pass | 0.4 s |

## lint

- Command: `uv run ruff check .`
- Blocking: yes
- Result: passed (exit 0, 0.1 s)

```text
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
All checks passed!
```

## format

- Command: `uv run ruff format --check .`
- Blocking: yes
- Result: passed (exit 0, 0.1 s)

```text
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
460 files already formatted
```

## types

- Command: `uv run mypy`
- Blocking: yes
- Result: passed (exit 0, 2.9 s)

```text
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
Success: no issues found in 77 source files
```

## tests

- Command: `uv run pytest -q`
- Blocking: yes
- Result: passed (exit 0, 111.0 s)

```text
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
........................................................................ [ 14%]
........................................................................ [ 28%]
........................................................................ [ 43%]
........................................................................ [ 57%]
........................................................................ [ 72%]
................................................................s....... [ 86%]
.................................................................        [100%]
496 passed, 1 skipped in 110.40s (0:01:50)
```

## file length

- Command: `uv run python scripts/check_file_length.py`
- Blocking: yes
- Result: passed (exit 0, 0.1 s)

```text
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
file length OK: no file over 600 lines under src, tests, scripts
```

## docs: references

- Command: `uv run python scripts/generate_docs.py --check`
- Blocking: yes
- Result: passed (exit 0, 0.4 s)

```text
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
```

Summary: 6 passed, 0 failed (0 blocking).
