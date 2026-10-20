# Checks

Risk tier: high: no `[checks_policy]`.

Replayed by Ariane on commit `7b13bdaf0c2bc5a1e899469b01e200a2dcffae93`.

Each check was replayed in its own clean working tree at `7b13bdaf0c2bc5a1e899469b01e200a2dcffae93`, after the setup.

| Check | Blocking | Result | Duration |
| --- | --- | --- | --- |
| lint | yes | pass | 0.2 s |
| format | yes | pass | 0.2 s |
| types | yes | pass | 4.3 s |
| tests | yes | pass | 138.8 s |
| file length | yes | pass | 0.2 s |
| docs: references | yes | pass | 0.5 s |

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
754 files already formatted
```

## types

- Command: `uv run mypy`
- Blocking: yes
- Result: passed (exit 0, 4.3 s)

```text
Success: no issues found in 119 source files
```

## tests

- Command: `uv run pytest -q`
- Blocking: yes
- Result: passed (exit 0, 138.8 s)

```text
bringing up nodes...
bringing up nodes...

........................................................................ [  7%]
........................................................................ [ 15%]
........................................................................ [ 22%]
........................................................................ [ 30%]
........................................................................ [ 37%]
.......................................s................................ [ 45%]
........................................................................ [ 52%]
........................................................................ [ 60%]
........................................................................ [ 67%]
........................................................................ [ 75%]
........................................................................ [ 82%]
........................................................................ [ 90%]
...................................................s.................... [ 97%]
......................                                                   [100%]
956 passed, 2 skipped in 137.92s (0:02:17)
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
- Result: passed (exit 0, 0.5 s)

```text

```

Summary: 6 passed, 0 failed (0 blocking).
