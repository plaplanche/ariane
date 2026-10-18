# Checks

Replayed by Ariane on commit `4328eb3a09a40f65e446afd7e26a87aa5780cbaf`.

Each check was replayed in its own clean working tree at `4328eb3a09a40f65e446afd7e26a87aa5780cbaf`, after the setup.

| Check | Blocking | Result | Duration |
| --- | --- | --- | --- |
| lint | yes | pass | 0.1 s |
| format | yes | pass | 0.1 s |
| types | yes | pass | 3.3 s |
| tests | yes | pass | 359.9 s |
| file length | yes | pass | 0.1 s |
| docs: references | yes | pass | 0.4 s |

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
609 files already formatted
```

## types

- Command: `uv run mypy`
- Blocking: yes
- Result: passed (exit 0, 3.3 s)

```text
Success: no issues found in 97 source files
```

## tests

- Command: `uv run pytest -q`
- Blocking: yes
- Result: passed (exit 0, 359.9 s)

```text
........................................................................ [ 10%]
........................................................................ [ 20%]
........................................................................ [ 30%]
.............s.......................................................... [ 40%]
........................................................................ [ 50%]
........................................................................ [ 61%]
........................................................................ [ 71%]
........................................................................ [ 81%]
.....................................................s.................. [ 91%]
............................................................             [100%]
706 passed, 2 skipped in 359.08s (0:05:59)
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
