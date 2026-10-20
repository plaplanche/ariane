# Checks

Replayed by Ariane on commit `8f689a04cebadc0b9e7c905de90d4c35531d327b`.

Each check was replayed in its own clean working tree at `8f689a04cebadc0b9e7c905de90d4c35531d327b`, after the setup.

| Check | Blocking | Result | Duration |
| --- | --- | --- | --- |
| lint | yes | pass | 0.2 s |
| format | yes | pass | 0.2 s |
| types | yes | pass | 6.8 s |
| tests | yes | pass | 186.1 s |
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
704 files already formatted
```

## types

- Command: `uv run mypy`
- Blocking: yes
- Result: passed (exit 0, 6.8 s)

```text
Success: no issues found in 111 source files
```

## tests

- Command: `uv run pytest -q`
- Blocking: yes
- Result: passed (exit 0, 186.1 s)

```text
bringing up nodes...
bringing up nodes...

........................................................................ [  8%]
........................................................................ [ 16%]
............................s........................................... [ 25%]
........................................................................ [ 33%]
........................................................................ [ 42%]
........................................................................ [ 50%]
........................................................................ [ 58%]
........................................................................ [ 67%]
........................................................................ [ 75%]
........................................................................ [ 84%]
........................................................................ [ 92%]
................s..............................................          [100%]
853 passed, 2 skipped in 184.68s (0:03:04)
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
