# Checks

Risk tier: high: no `[checks_policy]`.

Replayed by Ariane on commit `d69b3d2f06199720398c6c5e6c70cc6c4e625fa9`.

Each check was replayed in its own clean working tree at `d69b3d2f06199720398c6c5e6c70cc6c4e625fa9`, after the setup.

| Check | Blocking | Result | Duration |
| --- | --- | --- | --- |
| lint | yes | pass | 0.1 s |
| format | yes | pass | 0.1 s |
| types | yes | pass | 4.7 s |
| tests | yes | pass | 143.5 s |
| file length | yes | pass | 0.1 s |
| docs: references | yes | pass | 0.6 s |

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
746 files already formatted
```

## types

- Command: `uv run mypy`
- Blocking: yes
- Result: passed (exit 0, 4.7 s)

```text
Success: no issues found in 117 source files
```

## tests

- Command: `uv run pytest -q`
- Blocking: yes
- Result: passed (exit 0, 143.5 s)

```text
bringing up nodes...
bringing up nodes...

........................................................................ [  7%]
........................................................................ [ 15%]
........................................................................ [ 22%]
........................................................................ [ 30%]
..................................................s..................... [ 38%]
........................................................................ [ 45%]
........................................................................ [ 53%]
........................................................................ [ 60%]
........................................................................ [ 68%]
........................................................................ [ 76%]
........................................................................ [ 83%]
........................................................................ [ 91%]
.................................................................s...... [ 98%]
..........                                                               [100%]
944 passed, 2 skipped in 142.49s (0:02:22)
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
- Result: passed (exit 0, 0.6 s)

```text

```

Summary: 6 passed, 0 failed (0 blocking).
