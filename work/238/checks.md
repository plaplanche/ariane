# Checks

Risk tier: high: no `[checks_policy]`.

Replayed by Ariane on commit `50f7a7f77a77aa3338329fce1f91ef4a0aed2130`.

Each check was replayed in its own clean working tree at `50f7a7f77a77aa3338329fce1f91ef4a0aed2130`, after the setup.

| Check | Blocking | Result | Duration |
| --- | --- | --- | --- |
| lint | yes | pass | 0.1 s |
| format | yes | pass | 0.1 s |
| types | yes | pass | 3.8 s |
| tests | yes | pass | 153.0 s |
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
815 files already formatted
```

## types

- Command: `uv run mypy`
- Blocking: yes
- Result: passed (exit 0, 3.8 s)

```text
Success: no issues found in 136 source files
```

## tests

- Command: `uv run pytest -q`
- Blocking: yes
- Result: passed (exit 0, 153.0 s)

```text
bringing up nodes...
bringing up nodes...

........................................................................ [  6%]
........................................................................ [ 13%]
........................................................................ [ 20%]
....................................................s................... [ 26%]
........................................................................ [ 33%]
........................................................................ [ 40%]
........................................................................ [ 46%]
........................................................................ [ 53%]
........................................................................ [ 60%]
........................................................................ [ 66%]
........................................................................ [ 73%]
........................................................................ [ 80%]
........................................................................ [ 86%]
........................................................................ [ 93%]
........................................s............................... [100%]
1078 passed, 2 skipped in 152.30s (0:02:32)
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
