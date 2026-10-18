# Checks

Replayed by Ariane on commit `9cdc6910dc814b011bbf853c5d6d8f047a9a2035`.

Each check was replayed in its own clean working tree at `9cdc6910dc814b011bbf853c5d6d8f047a9a2035`, after the setup.

| Check | Blocking | Result | Duration |
| --- | --- | --- | --- |
| lint | yes | pass | 0.2 s |
| format | yes | pass | 0.2 s |
| types | yes | pass | 3.9 s |
| tests | yes | pass | 131.1 s |
| file length | yes | pass | 0.1 s |
| docs: references | yes | pass | 0.4 s |

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
643 files already formatted
```

## types

- Command: `uv run mypy`
- Blocking: yes
- Result: passed (exit 0, 3.9 s)

```text
Success: no issues found in 101 source files
```

## tests

- Command: `uv run pytest -q`
- Blocking: yes
- Result: passed (exit 0, 131.1 s)

```text
bringing up nodes...
bringing up nodes...

........................................................................ [  9%]
........................................................................ [ 19%]
........................................................................ [ 29%]
............................s........................................... [ 39%]
........................................................................ [ 48%]
........................................................................ [ 58%]
........................................................................ [ 68%]
........................................................................ [ 78%]
........................................................................ [ 88%]
...........................................s............................ [ 97%]
...............                                                          [100%]
733 passed, 2 skipped in 130.23s (0:02:10)
```

## file length

- Command: `uv run python scripts/check_file_length.py`
- Blocking: yes
- Result: passed (exit 0, 0.1 s)

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
