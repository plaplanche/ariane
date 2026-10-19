# Checks

Replayed by Ariane on commit `a709edfe518a8dc1d79f8fc0de654061dfdefc25`.

Each check was replayed in its own clean working tree at `a709edfe518a8dc1d79f8fc0de654061dfdefc25`, after the setup.

| Check | Blocking | Result | Duration |
| --- | --- | --- | --- |
| lint | yes | pass | 0.1 s |
| format | yes | pass | 0.2 s |
| types | yes | pass | 4.5 s |
| tests | yes | pass | 116.8 s |
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
- Result: passed (exit 0, 0.2 s)

```text
693 files already formatted
```

## types

- Command: `uv run mypy`
- Blocking: yes
- Result: passed (exit 0, 4.5 s)

```text
Success: no issues found in 110 source files
```

## tests

- Command: `uv run pytest -q`
- Blocking: yes
- Result: passed (exit 0, 116.8 s)

```text
bringing up nodes...
bringing up nodes...

........................................................................ [  8%]
........................................................................ [ 17%]
........................................................................ [ 25%]
........................................s............................... [ 34%]
........................................................................ [ 42%]
........................................................................ [ 51%]
........................................................................ [ 59%]
........................................................................ [ 68%]
........................................................................ [ 76%]
........................................................................ [ 85%]
.........................s.............................................. [ 93%]
...................................................                      [100%]
841 passed, 2 skipped in 116.04s (0:01:56)
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
