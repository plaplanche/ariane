# Checks

Replayed by Ariane on commit `8aaad267593e205221de0b0492b646543e81b190`.

Each check was replayed in its own clean working tree at `8aaad267593e205221de0b0492b646543e81b190`, after the setup.

| Check | Blocking | Result | Duration |
| --- | --- | --- | --- |
| lint | yes | pass | 0.1 s |
| format | yes | pass | 0.1 s |
| types | yes | pass | 2.9 s |
| tests | yes | pass | 280.8 s |
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
590 files already formatted
```

## types

- Command: `uv run mypy`
- Blocking: yes
- Result: passed (exit 0, 2.9 s)

```text
Success: no issues found in 94 source files
```

## tests

- Command: `uv run pytest -q`
- Blocking: yes
- Result: passed (exit 0, 280.8 s)

```text
........................................................................ [ 10%]
........................................................................ [ 21%]
......................................................................s. [ 31%]
........................................................................ [ 42%]
........................................................................ [ 53%]
........................................................................ [ 63%]
........................................................................ [ 74%]
........................................................................ [ 85%]
.....................s.................................................. [ 95%]
............................                                             [100%]
674 passed, 2 skipped in 280.12s (0:04:40)
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
