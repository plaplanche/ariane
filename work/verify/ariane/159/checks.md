# Checks

Replayed by Ariane on commit `eb008d89b8f5aafa00f5c9f6d65d550b91928517`.

Each check was replayed in its own clean working tree at `eb008d89b8f5aafa00f5c9f6d65d550b91928517`, after the setup.

| Check | Blocking | Result | Duration |
| --- | --- | --- | --- |
| lint | yes | pass | 0.1 s |
| format | yes | pass | 0.2 s |
| types | yes | pass | 4.0 s |
| tests | yes | pass | 286.1 s |
| file length | yes | pass | 0.2 s |
| docs: references | yes | pass | 0.5 s |

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
594 files already formatted
```

## types

- Command: `uv run mypy`
- Blocking: yes
- Result: passed (exit 0, 4.0 s)

```text
Success: no issues found in 94 source files
```

## tests

- Command: `uv run pytest -q`
- Blocking: yes
- Result: passed (exit 0, 286.1 s)

```text
........................................................................ [ 10%]
........................................................................ [ 21%]
........................................................................ [ 31%]
....s................................................................... [ 42%]
........................................................................ [ 52%]
........................................................................ [ 63%]
........................................................................ [ 73%]
........................................................................ [ 84%]
...........................s............................................ [ 95%]
..................................                                       [100%]
680 passed, 2 skipped in 285.40s (0:04:45)
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
- Result: passed (exit 0, 0.5 s)

```text

```

Summary: 6 passed, 0 failed (0 blocking).
