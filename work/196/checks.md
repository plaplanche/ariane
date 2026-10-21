# Checks

Risk tier: high: no `[checks_policy]`.

Replayed by Ariane on commit `3b3653771a9cf4e5bd87543d780430aa6beb53e0`.

Each check was replayed in its own clean working tree at `3b3653771a9cf4e5bd87543d780430aa6beb53e0`, after the setup.

| Check | Blocking | Result | Duration |
| --- | --- | --- | --- |
| lint | yes | pass | 0.2 s |
| format | yes | pass | 0.2 s |
| types | yes | pass | 4.2 s |
| tests | yes | pass | 132.8 s |
| file length | yes | pass | 0.2 s |
| docs: references | yes | pass | 0.5 s |

## lint

- Command: `uv run ruff check .`
- Blocking: yes
- Result: passed (exit 0, 0.2 s)

```text
All checks passed!
```

## format

- Command: `uv run ruff format --check .`
- Blocking: yes
- Result: passed (exit 0, 0.2 s)

```text
753 files already formatted
```

## types

- Command: `uv run mypy`
- Blocking: yes
- Result: passed (exit 0, 4.2 s)

```text
Success: no issues found in 119 source files
```

## tests

- Command: `uv run pytest -q`
- Blocking: yes
- Result: passed (exit 0, 132.8 s)

```text
bringing up nodes...
bringing up nodes...

........................................................................ [  7%]
........................................................................ [ 15%]
........................................................................ [ 22%]
........................................................................ [ 30%]
........................................................................ [ 37%]
....................................s................................... [ 45%]
........................................................................ [ 52%]
........................................................................ [ 60%]
........................................................................ [ 67%]
........................................................................ [ 75%]
........................................................................ [ 82%]
........................................................................ [ 90%]
..........................................................s............. [ 97%]
......................                                                   [100%]
956 passed, 2 skipped in 131.86s (0:02:11)
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
