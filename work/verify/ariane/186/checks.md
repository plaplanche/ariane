# Checks

Risk tier: high: no `[checks_policy]`.

Replayed by Ariane on commit `eeb3f33ee2c2e1b4be4a8dc0ded197ccc9574ad8`.

Each check was replayed in its own clean working tree at `eeb3f33ee2c2e1b4be4a8dc0ded197ccc9574ad8`, after the setup.

| Check | Blocking | Result | Duration |
| --- | --- | --- | --- |
| lint | yes | pass | 0.2 s |
| format | yes | pass | 0.2 s |
| types | yes | pass | 4.2 s |
| tests | yes | pass | 136.6 s |
| file length | yes | pass | 0.2 s |
| docs: references | yes | pass | 0.6 s |

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
744 files already formatted
```

## types

- Command: `uv run mypy`
- Blocking: yes
- Result: passed (exit 0, 4.2 s)

```text
Success: no issues found in 117 source files
```

## tests

- Command: `uv run pytest -q`
- Blocking: yes
- Result: passed (exit 0, 136.6 s)

```text
bringing up nodes...
bringing up nodes...

........................................................................ [  7%]
........................................................................ [ 15%]
........................................................................ [ 22%]
........................................................................ [ 30%]
........................................................................ [ 38%]
.s...................................................................... [ 45%]
........................................................................ [ 53%]
........................................................................ [ 61%]
........................................................................ [ 68%]
........................................................................ [ 76%]
........................................................................ [ 84%]
........................................................................ [ 91%]
..............................................................s......... [ 99%]
....                                                                     [100%]
938 passed, 2 skipped in 135.63s (0:02:15)
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
- Result: passed (exit 0, 0.6 s)

```text

```

Summary: 6 passed, 0 failed (0 blocking).
