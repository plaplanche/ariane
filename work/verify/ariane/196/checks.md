# Checks

Risk tier: high: no `[checks_policy]`.

Replayed by Ariane on commit `12ce7eb6d964e6e2df32b1692d8ba423d13bfc63`.

Each check was replayed in its own clean working tree at `12ce7eb6d964e6e2df32b1692d8ba423d13bfc63`, after the setup.

| Check | Blocking | Result | Duration |
| --- | --- | --- | --- |
| lint | yes | pass | 0.1 s |
| format | yes | pass | 0.1 s |
| types | yes | pass | 4.7 s |
| tests | yes | pass | 162.9 s |
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
771 files already formatted
```

## types

- Command: `uv run mypy`
- Blocking: yes
- Result: passed (exit 0, 4.7 s)

```text
Success: no issues found in 124 source files
```

## tests

- Command: `uv run pytest -q`
- Blocking: yes
- Result: passed (exit 0, 162.9 s)

```text
bringing up nodes...
bringing up nodes...

........................................................................ [  7%]
........................................................................ [ 14%]
........................................................................ [ 21%]
s....................................................................... [ 28%]
........................................................................ [ 35%]
........................................................................ [ 43%]
........................................................................ [ 50%]
........................................................................ [ 57%]
........................................................................ [ 64%]
........................................................................ [ 71%]
........................................................................ [ 79%]
........................................................................ [ 86%]
........................................................................ [ 93%]
......................s...........................................       [100%]
1000 passed, 2 skipped in 162.03s (0:02:42)
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
