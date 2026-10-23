# Checks

Risk tier: high: no `[checks_policy]`.

Replayed by Ariane on commit `5f59be3431bb477877efe6f8611baefacb16472b`.

Each check was replayed in its own clean working tree at `5f59be3431bb477877efe6f8611baefacb16472b`, after the setup.

| Check | Blocking | Result | Duration |
| --- | --- | --- | --- |
| lint | yes | pass | 0.1 s |
| format | yes | pass | 0.2 s |
| types | yes | pass | 6.5 s |
| types (Windows) | yes | pass | 6.1 s |
| tests | yes | pass | 226.8 s |
| file length | yes | pass | 0.1 s |
| docs: references | yes | pass | 0.8 s |

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
832 files already formatted
```

## types

- Command: `uv run mypy`
- Blocking: yes
- Result: passed (exit 0, 6.5 s)

```text
Success: no issues found in 138 source files
```

## types (Windows)

- Command: `uv run mypy --platform win32`
- Blocking: yes
- Result: passed (exit 0, 6.1 s)

```text
Success: no issues found in 138 source files
```

## tests

- Command: `uv run pytest -q`
- Blocking: yes
- Result: passed (exit 0, 226.8 s)

```text
bringing up nodes...
bringing up nodes...

........................................................................ [  6%]
........................................................................ [ 13%]
........................................................................ [ 19%]
....................................s................................... [ 26%]
........................................................................ [ 32%]
........................................................................ [ 39%]
........................................................................ [ 45%]
........................................................................ [ 52%]
........................................................................ [ 58%]
........................................................................ [ 65%]
........................................................................ [ 71%]
........................................................................ [ 78%]
........................................................................ [ 84%]
........................................................................ [ 91%]
..............s......................................................... [ 97%]
........................                                                 [100%]
1102 passed, 2 skipped in 225.69s (0:03:45)
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
- Result: passed (exit 0, 0.8 s)

```text

```

Summary: 7 passed, 0 failed (0 blocking).
