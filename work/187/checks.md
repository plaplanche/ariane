# Checks

Replayed by Ariane on commit `fcdf515d21bddc84b27ad530507c0fda8d472d2b`.

Each check was replayed in its own clean working tree at `fcdf515d21bddc84b27ad530507c0fda8d472d2b`, after the setup.

| Check | Blocking | Result | Duration |
| --- | --- | --- | --- |
| lint | yes | pass | 0.1 s |
| format | yes | pass | 0.1 s |
| types | yes | pass | 3.7 s |
| tests | yes | pass | 102.7 s |
| file length | yes | pass | 0.1 s |
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
- Result: passed (exit 0, 0.1 s)

```text
607 files already formatted
```

## types

- Command: `uv run mypy`
- Blocking: yes
- Result: passed (exit 0, 3.7 s)

```text
Success: no issues found in 96 source files
```

## tests

- Command: `uv run pytest -q`
- Blocking: yes
- Result: passed (exit 0, 102.7 s)

```text
bringing up nodes...
bringing up nodes...

........................................................................ [ 10%]
........................................................................ [ 20%]
........................................................................ [ 31%]
........s............................................................... [ 41%]
........................................................................ [ 51%]
........................................................................ [ 62%]
........................................................................ [ 72%]
........................................................................ [ 83%]
........................................s............................... [ 93%]
.............................................                            [100%]
691 passed, 2 skipped in 101.75s (0:01:41)
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
