# Checks

Replayed by Ariane on commit `5c9a87cadab24973e1782d6500d1306fa3d37c4c`.

Each check was replayed in its own clean working tree at `5c9a87cadab24973e1782d6500d1306fa3d37c4c`, after the setup.

| Check | Blocking | Result | Duration |
| --- | --- | --- | --- |
| lint | yes | pass | 0.2 s |
| format | yes | pass | 0.1 s |
| types | yes | pass | 4.4 s |
| tests | yes | pass | 246.6 s |
| file length | yes | pass | 0.1 s |
| docs: references | yes | pass | 0.4 s |

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
572 files already formatted
```

## types

- Command: `uv run mypy`
- Blocking: yes
- Result: passed (exit 0, 4.4 s)

```text
Success: no issues found in 91 source files
```

## tests

- Command: `uv run pytest -q`
- Blocking: yes
- Result: passed (exit 0, 246.6 s)

```text
........................................................................ [ 11%]
........................................................................ [ 22%]
.........................s.............................................. [ 34%]
........................................................................ [ 45%]
........................................................................ [ 57%]
........................................................................ [ 68%]
........................................................................ [ 79%]
................................................s....................... [ 91%]
.......................................................                  [100%]
629 passed, 2 skipped in 245.91s (0:04:05)
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
- Result: passed (exit 0, 0.4 s)

```text

```

Summary: 6 passed, 0 failed (0 blocking).
