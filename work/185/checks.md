# Checks

Replayed by Ariane on commit `394d4c475e96dee56e6081455ca67d0e716a11a0`.

Each check was replayed in its own clean working tree at `394d4c475e96dee56e6081455ca67d0e716a11a0`, after the setup.

| Check | Blocking | Result | Duration |
| --- | --- | --- | --- |
| lint | yes | pass | 0.3 s |
| format | yes | pass | 0.3 s |
| types | yes | pass | 7.2 s |
| tests | yes | pass | 250.7 s |
| file length | yes | pass | 0.2 s |
| docs: references | yes | pass | 1.0 s |

## lint

- Command: `uv run ruff check .`
- Blocking: yes
- Result: passed (exit 0, 0.3 s)

```text
All checks passed!
```

## format

- Command: `uv run ruff format --check .`
- Blocking: yes
- Result: passed (exit 0, 0.3 s)

```text
723 files already formatted
```

## types

- Command: `uv run mypy`
- Blocking: yes
- Result: passed (exit 0, 7.2 s)

```text
Success: no issues found in 114 source files
```

## tests

- Command: `uv run pytest -q`
- Blocking: yes
- Result: passed (exit 0, 250.7 s)

```text
bringing up nodes...
bringing up nodes...

........................................................................ [  7%]
........................................................................ [ 15%]
........................................................................ [ 23%]
................................................................s....... [ 31%]
........................................................................ [ 39%]
........................................................................ [ 47%]
........................................................................ [ 55%]
........................................................................ [ 63%]
........................................................................ [ 71%]
........................................................................ [ 79%]
........................................................................ [ 87%]
........s............................................................... [ 95%]
........................................                                 [100%]
902 passed, 2 skipped in 249.15s (0:04:09)
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
- Result: passed (exit 0, 1.0 s)

```text

```

Summary: 6 passed, 0 failed (0 blocking).
