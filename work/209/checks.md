# Checks

Replayed by Ariane on commit `9a0316e5afb45a1803632f1861071e7c313e6beb`.

Each check was replayed in its own clean working tree at `9a0316e5afb45a1803632f1861071e7c313e6beb`, after the setup.

| Check | Blocking | Result | Duration |
| --- | --- | --- | --- |
| lint | yes | pass | 0.1 s |
| format | yes | pass | 0.1 s |
| types | yes | pass | 3.7 s |
| tests | yes | pass | 111.6 s |
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
687 files already formatted
```

## types

- Command: `uv run mypy`
- Blocking: yes
- Result: passed (exit 0, 3.7 s)

```text
Success: no issues found in 109 source files
```

## tests

- Command: `uv run pytest -q`
- Blocking: yes
- Result: passed (exit 0, 111.6 s)

```text
bringing up nodes...
bringing up nodes...

........................................................................ [  8%]
........................................................................ [ 17%]
........................................................................ [ 25%]
.........................................s.............................. [ 34%]
........................................................................ [ 42%]
........................................................................ [ 51%]
........................................................................ [ 60%]
........................................................................ [ 68%]
........................................................................ [ 77%]
........................................................................ [ 85%]
................s....................................................... [ 94%]
...............................................                          [100%]
837 passed, 2 skipped in 110.86s (0:01:50)
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
