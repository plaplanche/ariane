# Checks

Replayed by Ariane on commit `db724b9198fa3103d1fbd8d260a2f6d7ab332fb2`.

Each check was replayed in its own clean working tree at `db724b9198fa3103d1fbd8d260a2f6d7ab332fb2`, after the setup.

| Check | Blocking | Result | Duration |
| --- | --- | --- | --- |
| lint | yes | pass | 0.1 s |
| format | yes | pass | 0.1 s |
| types | yes | pass | 3.9 s |
| tests | yes | pass | 123.8 s |
| file length | yes | pass | 0.1 s |
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
- Result: passed (exit 0, 0.1 s)

```text
698 files already formatted
```

## types

- Command: `uv run mypy`
- Blocking: yes
- Result: passed (exit 0, 3.9 s)

```text
Success: no issues found in 111 source files
```

## tests

- Command: `uv run pytest -q`
- Blocking: yes
- Result: passed (exit 0, 123.8 s)

```text
bringing up nodes...
bringing up nodes...

........................................................................ [  8%]
........................................................................ [ 16%]
..............................................s......................... [ 25%]
........................................................................ [ 33%]
........................................................................ [ 42%]
........................................................................ [ 50%]
........................................................................ [ 59%]
........................................................................ [ 67%]
........................................................................ [ 75%]
........................................................................ [ 84%]
...........................s............................................ [ 92%]
.............................................................            [100%]
851 passed, 2 skipped in 123.09s (0:02:03)
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
- Result: passed (exit 0, 0.5 s)

```text

```

Summary: 6 passed, 0 failed (0 blocking).
