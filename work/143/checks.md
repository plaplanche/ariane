# Checks

Replayed by Ariane on commit `7fd19a0a2de536592da7c5592c7e62afdaa8676e`.

Each check was replayed in its own clean working tree at `7fd19a0a2de536592da7c5592c7e62afdaa8676e`, after the setup.

| Check | Blocking | Result | Duration |
| --- | --- | --- | --- |
| lint | yes | pass | 0.1 s |
| format | yes | pass | 0.1 s |
| types | yes | pass | 3.6 s |
| tests | yes | pass | 118.0 s |
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
662 files already formatted
```

## types

- Command: `uv run mypy`
- Blocking: yes
- Result: passed (exit 0, 3.6 s)

```text
Success: no issues found in 105 source files
```

## tests

- Command: `uv run pytest -q`
- Blocking: yes
- Result: passed (exit 0, 118.0 s)

```text
bringing up nodes...
bringing up nodes...

........................................................................ [  9%]
........................................................................ [ 18%]
...............................................s........................ [ 27%]
........................................................................ [ 36%]
........................................................................ [ 46%]
........................................................................ [ 55%]
........................................................................ [ 64%]
........................................................................ [ 73%]
........................................................................ [ 82%]
........................................................................ [ 92%]
..........................s...................................           [100%]
780 passed, 2 skipped in 117.15s (0:01:57)
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
