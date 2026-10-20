# Checks

Risk tier: high: no `[checks_policy]`.

Replayed by Ariane on commit `04c992c26fc55f6f73b15de46344a88e5d54373c`.

Each check was replayed in its own clean working tree at `04c992c26fc55f6f73b15de46344a88e5d54373c`, after the setup.

| Check | Blocking | Result | Duration |
| --- | --- | --- | --- |
| lint | yes | pass | 0.1 s |
| format | yes | pass | 0.1 s |
| types | yes | pass | 4.4 s |
| tests | yes | pass | 138.2 s |
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
756 files already formatted
```

## types

- Command: `uv run mypy`
- Blocking: yes
- Result: passed (exit 0, 4.4 s)

```text
Success: no issues found in 119 source files
```

## tests

- Command: `uv run pytest -q`
- Blocking: yes
- Result: passed (exit 0, 138.2 s)

```text
bringing up nodes...
bringing up nodes...

........................................................................ [  7%]
........................................................................ [ 14%]
........................................................................ [ 22%]
........................................................................ [ 29%]
........................................................................ [ 37%]
........................................................................ [ 44%]
s....................................................................... [ 52%]
........................................................................ [ 59%]
........................................................................ [ 67%]
........................................................................ [ 74%]
........................................................................ [ 82%]
........................................................................ [ 89%]
.s...................................................................... [ 97%]
..........................                                               [100%]
960 passed, 2 skipped in 137.41s (0:02:17)
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
