# Checks

Risk tier: high: no `[checks_policy]`.

Replayed by Ariane on commit `73b51519e4bf2d0bbb2a1164cad14b04ced14a88`.

Each check was replayed in its own clean working tree at `73b51519e4bf2d0bbb2a1164cad14b04ced14a88`, after the setup.

| Check | Blocking | Result | Duration |
| --- | --- | --- | --- |
| lint | yes | pass | 0.2 s |
| format | yes | pass | 0.1 s |
| types | yes | pass | 4.8 s |
| tests | yes | pass | 172.8 s |
| file length | yes | pass | 0.1 s |
| docs: references | yes | pass | 1.4 s |

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
- Result: passed (exit 0, 0.1 s)

```text
748 files already formatted
```

## types

- Command: `uv run mypy`
- Blocking: yes
- Result: passed (exit 0, 4.8 s)

```text
Success: no issues found in 119 source files
```

## tests

- Command: `uv run pytest -q`
- Blocking: yes
- Result: passed (exit 0, 172.8 s)

```text
bringing up nodes...
bringing up nodes...

........................................................................ [  7%]
........................................................................ [ 15%]
........................................................................ [ 22%]
........................................................................ [ 30%]
......................................................s................. [ 37%]
........................................................................ [ 45%]
........................................................................ [ 52%]
........................................................................ [ 60%]
........................................................................ [ 68%]
........................................................................ [ 75%]
........................................................................ [ 83%]
........................................................................ [ 90%]
.........................................s.............................. [ 98%]
................                                                         [100%]
950 passed, 2 skipped in 171.81s (0:02:51)
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
- Result: passed (exit 0, 1.4 s)

```text

```

Summary: 6 passed, 0 failed (0 blocking).
