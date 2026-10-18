# Checks

Replayed by Ariane on commit `a56f07501612d7efff84f1fe2b16c3ed9c75b4d8`.

Each check was replayed in its own clean working tree at `a56f07501612d7efff84f1fe2b16c3ed9c75b4d8`, after the setup.

| Check | Blocking | Result | Duration |
| --- | --- | --- | --- |
| lint | yes | pass | 0.2 s |
| format | yes | pass | 0.2 s |
| types | yes | pass | 4.0 s |
| tests | yes | pass | 397.5 s |
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
613 files already formatted
```

## types

- Command: `uv run mypy`
- Blocking: yes
- Result: passed (exit 0, 4.0 s)

```text
Success: no issues found in 97 source files
```

## tests

- Command: `uv run pytest -q`
- Blocking: yes
- Result: passed (exit 0, 397.5 s)

```text
........................................................................ [ 10%]
........................................................................ [ 20%]
........................................................................ [ 30%]
.............s.......................................................... [ 40%]
........................................................................ [ 50%]
........................................................................ [ 60%]
........................................................................ [ 70%]
........................................................................ [ 81%]
........................................................s............... [ 91%]
...............................................................          [100%]
709 passed, 2 skipped in 396.70s (0:06:36)
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
