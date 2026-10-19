# Checks

Replayed by Ariane on commit `41c0aa806ac26323054240573b7cd40320a8e059`.

Each check was replayed in its own clean working tree at `41c0aa806ac26323054240573b7cd40320a8e059`, after the setup.

| Check | Blocking | Result | Duration |
| --- | --- | --- | --- |
| lint | yes | pass | 0.1 s |
| format | yes | pass | 0.1 s |
| types | yes | pass | 3.5 s |
| tests | yes | pass | 102.9 s |
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
674 files already formatted
```

## types

- Command: `uv run mypy`
- Blocking: yes
- Result: passed (exit 0, 3.5 s)

```text
Success: no issues found in 107 source files
```

## tests

- Command: `uv run pytest -q`
- Blocking: yes
- Result: passed (exit 0, 102.9 s)

```text
bringing up nodes...
bringing up nodes...

........................................................................ [  8%]
........................................................................ [ 17%]
........................................................................ [ 26%]
........................................................................ [ 35%]
..........................s............................................. [ 44%]
........................................................................ [ 53%]
........................................................................ [ 62%]
........................................................................ [ 71%]
........................................................................ [ 80%]
........................................................................ [ 89%]
.................................................................s...... [ 98%]
............                                                             [100%]
802 passed, 2 skipped in 102.09s (0:01:42)
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
