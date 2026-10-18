# Checks

Replayed by Ariane on commit `6a04bd7db970eeaa6af2d14caa1181100d35e19f`.

Each check was replayed in its own clean working tree at `6a04bd7db970eeaa6af2d14caa1181100d35e19f`, after the setup.

| Check | Blocking | Result | Duration |
| --- | --- | --- | --- |
| lint | yes | pass | 0.2 s |
| format | yes | pass | 0.2 s |
| types | yes | pass | 6.8 s |
| tests | yes | pass | 109.3 s |
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
634 files already formatted
```

## types

- Command: `uv run mypy`
- Blocking: yes
- Result: passed (exit 0, 6.8 s)

```text
Success: no issues found in 99 source files
```

## tests

- Command: `uv run pytest -q`
- Blocking: yes
- Result: passed (exit 0, 109.3 s)

```text
bringing up nodes...
bringing up nodes...

........................................................................ [  9%]
........................................................................ [ 19%]
.........................................................s.............. [ 29%]
........................................................................ [ 39%]
........................................................................ [ 49%]
........................................................................ [ 59%]
........................................................................ [ 69%]
........................................................................ [ 79%]
........................................................................ [ 89%]
..................................s..................................... [ 99%]
....                                                                     [100%]
722 passed, 2 skipped in 108.29s (0:01:48)
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
