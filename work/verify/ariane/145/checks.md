# Checks

Risk tier: high: no `[checks_policy]`.

Replayed by Ariane on commit `9547f51cf2814123a0dc58d3e98c8396b8ba7fda`.

Each check was replayed in its own clean working tree at `9547f51cf2814123a0dc58d3e98c8396b8ba7fda`, after the setup.

| Check | Blocking | Result | Duration |
| --- | --- | --- | --- |
| lint | yes | pass | 0.1 s |
| format | yes | pass | 0.2 s |
| types | yes | pass | 4.3 s |
| tests | yes | pass | 159.2 s |
| file length | yes | pass | 0.1 s |
| docs: references | yes | pass | 0.7 s |

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
746 files already formatted
```

## types

- Command: `uv run mypy`
- Blocking: yes
- Result: passed (exit 0, 4.3 s)

```text
Success: no issues found in 117 source files
```

## tests

- Command: `uv run pytest -q`
- Blocking: yes
- Result: passed (exit 0, 159.2 s)

```text
bringing up nodes...
bringing up nodes...

........................................................................ [  7%]
........................................................................ [ 15%]
........................................................................ [ 22%]
........................................................................ [ 30%]
.........................................s.............................. [ 38%]
........................................................................ [ 45%]
........................................................................ [ 53%]
........................................................................ [ 61%]
........................................................................ [ 68%]
........................................................................ [ 76%]
........................................................................ [ 83%]
...................................................s.................... [ 91%]
........................................................................ [ 99%]
........                                                                 [100%]
942 passed, 2 skipped in 158.36s (0:02:38)
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
- Result: passed (exit 0, 0.7 s)

```text

```

Summary: 6 passed, 0 failed (0 blocking).
