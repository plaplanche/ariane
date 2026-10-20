# Checks

Replayed by Ariane on commit `0ec3c7650665cdeb7f386867de54631d49a1e483`.

Each check was replayed in its own clean working tree at `0ec3c7650665cdeb7f386867de54631d49a1e483`, after the setup.

| Check | Blocking | Result | Duration |
| --- | --- | --- | --- |
| lint | yes | pass | 0.2 s |
| format | yes | pass | 0.2 s |
| types | yes | pass | 5.3 s |
| tests | yes | pass | 154.5 s |
| file length | yes | pass | 0.2 s |
| docs: references | yes | pass | 0.7 s |

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
710 files already formatted
```

## types

- Command: `uv run mypy`
- Blocking: yes
- Result: passed (exit 0, 5.3 s)

```text
Success: no issues found in 112 source files
```

## tests

- Command: `uv run pytest -q`
- Blocking: yes
- Result: passed (exit 0, 154.5 s)

```text
bringing up nodes...
bringing up nodes...

........................................................................ [  8%]
........................................................................ [ 16%]
........................................................................ [ 24%]
........................................................................ [ 32%]
...........................................s............................ [ 41%]
........................................................................ [ 49%]
........................................................................ [ 57%]
........................................................................ [ 65%]
........................................................................ [ 73%]
........................................................................ [ 82%]
........................................................................ [ 90%]
...........................................s............................ [ 98%]
..............                                                           [100%]
876 passed, 2 skipped in 153.20s (0:02:33)
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
- Result: passed (exit 0, 0.7 s)

```text

```

Summary: 6 passed, 0 failed (0 blocking).
