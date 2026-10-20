# Checks

Replayed by Ariane on commit `22273bb12679db5dd15bcb7ed59ea7315b656413`.

Each check was replayed in its own clean working tree at `22273bb12679db5dd15bcb7ed59ea7315b656413`, after the setup.

| Check | Blocking | Result | Duration |
| --- | --- | --- | --- |
| lint | yes | pass | 0.2 s |
| format | yes | pass | 0.2 s |
| types | yes | pass | 6.0 s |
| tests | yes | pass | 379.3 s |
| file length | yes | pass | 0.3 s |
| docs: references | yes | pass | 1.1 s |

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
727 files already formatted
```

## types

- Command: `uv run mypy`
- Blocking: yes
- Result: passed (exit 0, 6.0 s)

```text
Success: no issues found in 114 source files
```

## tests

- Command: `uv run pytest -q`
- Blocking: yes
- Result: passed (exit 0, 379.3 s)

```text
bringing up nodes...
bringing up nodes...

........................................................................ [  7%]
........................................................................ [ 15%]
........................................................................ [ 23%]
........................................................................ [ 31%]
........................................................................ [ 39%]
....................................................s................... [ 47%]
........................................................................ [ 55%]
........................................................................ [ 63%]
........................................................................ [ 71%]
........................................................................ [ 79%]
........................................................................ [ 87%]
......s................................................................. [ 95%]
.......................................                                  [100%]
901 passed, 2 skipped in 377.74s (0:06:17)
```

## file length

- Command: `uv run python scripts/check_file_length.py`
- Blocking: yes
- Result: passed (exit 0, 0.3 s)

```text
file length OK: no file over 600 lines under src, tests, scripts
```

## docs: references

- Command: `uv run python scripts/generate_docs.py --check`
- Blocking: yes
- Result: passed (exit 0, 1.1 s)

```text

```

Summary: 6 passed, 0 failed (0 blocking).
