# Checks

Risk tier: high: no `[checks_policy]`.

Replayed by Ariane on commit `09b16847e8acfa42a95738d209ae302b95c2a7d8`.

Each check was replayed in its own clean working tree at `09b16847e8acfa42a95738d209ae302b95c2a7d8`, after the setup.

| Check | Blocking | Result | Duration |
| --- | --- | --- | --- |
| lint | yes | pass | 0.1 s |
| format | yes | pass | 0.2 s |
| types | yes | pass | 4.3 s |
| tests | yes | pass | 139.9 s |
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
- Result: passed (exit 0, 0.2 s)

```text
771 files already formatted
```

## types

- Command: `uv run mypy`
- Blocking: yes
- Result: passed (exit 0, 4.3 s)

```text
Success: no issues found in 124 source files
```

## tests

- Command: `uv run pytest -q`
- Blocking: yes
- Result: passed (exit 0, 139.9 s)

```text
bringing up nodes...
bringing up nodes...

........................................................................ [  7%]
........................................................................ [ 14%]
........................................................................ [ 21%]
....................s................................................... [ 28%]
........................................................................ [ 35%]
........................................................................ [ 42%]
........................................................................ [ 50%]
........................................................................ [ 57%]
........................................................................ [ 64%]
........................................................................ [ 71%]
........................................................................ [ 78%]
........................................................................ [ 85%]
.......................................................................s [ 93%]
.....................................................................    [100%]
1003 passed, 2 skipped in 139.13s (0:02:19)
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
