# Checks

Replayed by Ariane on commit `af6c2987a83fff31112208281454a5f278b1b1a3`.

Each check was replayed in its own clean working tree at `af6c2987a83fff31112208281454a5f278b1b1a3`, after the setup.

| Check | Blocking | Result | Duration |
| --- | --- | --- | --- |
| lint | yes | pass | 0.1 s |
| format | yes | pass | 0.2 s |
| types | yes | pass | 6.1 s |
| tests | yes | pass | 156.2 s |
| file length | yes | pass | 0.1 s |
| docs: references | yes | pass | 0.8 s |

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
706 files already formatted
```

## types

- Command: `uv run mypy`
- Blocking: yes
- Result: passed (exit 0, 6.1 s)

```text
Success: no issues found in 112 source files
```

## tests

- Command: `uv run pytest -q`
- Blocking: yes
- Result: passed (exit 0, 156.2 s)

```text
bringing up nodes...
bringing up nodes...

........................................................................ [  8%]
........................................................................ [ 16%]
........................................................................ [ 24%]
........................................................................ [ 32%]
..............................................s......................... [ 41%]
........................................................................ [ 49%]
........................................................................ [ 57%]
........................................................................ [ 65%]
........................................................................ [ 73%]
........................................................................ [ 82%]
........................................................................ [ 90%]
........................................s............................... [ 98%]
............                                                             [100%]
874 passed, 2 skipped in 154.92s (0:02:34)
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
- Result: passed (exit 0, 0.8 s)

```text

```

Summary: 6 passed, 0 failed (0 blocking).
