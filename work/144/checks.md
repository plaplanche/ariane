# Checks

Replayed by Ariane on commit `5bcc95f3057198511f18d35773721c33dae397e4`.

Each check was replayed in its own clean working tree at `5bcc95f3057198511f18d35773721c33dae397e4`, after the setup.

| Check | Blocking | Result | Duration |
| --- | --- | --- | --- |
| lint | yes | pass | 0.1 s |
| format | yes | pass | 0.2 s |
| types | yes | pass | 2.7 s |
| tests | yes | pass | 346.6 s |
| file length | yes | pass | 0.2 s |
| docs: references | yes | pass | 0.4 s |

## lint

- Command: `uv run ruff check .`
- Blocking: yes
- Result: passed (exit 0, 0.1 s)

```text
All checks passed!
```

## format

- Command: `uv run ruff format --check .`
- Blocking: yes
- Result: passed (exit 0, 0.2 s)

```text
600 files already formatted
```

## types

- Command: `uv run mypy`
- Blocking: yes
- Result: passed (exit 0, 2.7 s)

```text
Success: no issues found in 95 source files
```

## tests

- Command: `uv run pytest -q`
- Blocking: yes
- Result: passed (exit 0, 346.6 s)

```text
........................................................................ [ 10%]
........................................................................ [ 20%]
........................................................................ [ 31%]
.............s.......................................................... [ 41%]
........................................................................ [ 52%]
........................................................................ [ 62%]
........................................................................ [ 72%]
........................................................................ [ 83%]
....................................s................................... [ 93%]
...........................................                              [100%]
689 passed, 2 skipped in 345.91s (0:05:45)
```

## file length

- Command: `uv run python scripts/check_file_length.py`
- Blocking: yes
- Result: passed (exit 0, 0.2 s)

```text
file length OK: no file over 600 lines under src, tests, scripts
```

## docs: references

- Command: `uv run python scripts/generate_docs.py --check`
- Blocking: yes
- Result: passed (exit 0, 0.4 s)

```text

```

Summary: 6 passed, 0 failed (0 blocking).
