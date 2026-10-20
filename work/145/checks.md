# Checks

Replayed by Ariane on commit `c6678fd9c370496447cd562fac307a0d6da8dd0a`.

Each check was replayed in its own clean working tree at `c6678fd9c370496447cd562fac307a0d6da8dd0a`, after the setup.

| Check | Blocking | Result | Duration |
| --- | --- | --- | --- |
| lint | yes | pass | 0.1 s |
| format | yes | pass | 0.2 s |
| types | yes | pass | 7.0 s |
| tests | yes | pass | 269.4 s |
| file length | yes | pass | 0.1 s |
| docs: references | yes | pass | 0.7 s |

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
723 files already formatted
```

## types

- Command: `uv run mypy`
- Blocking: yes
- Result: passed (exit 0, 7.0 s)

```text
Success: no issues found in 114 source files
```

## tests

- Command: `uv run pytest -q`
- Blocking: yes
- Result: passed (exit 0, 269.4 s)

```text
bringing up nodes...
bringing up nodes...

........................................................................ [  8%]
........................................................................ [ 16%]
........................................................................ [ 24%]
........................................................................ [ 32%]
........................................................................ [ 40%]
...............................................s........................ [ 48%]
........................................................................ [ 56%]
........................................................................ [ 64%]
........................................................................ [ 72%]
........................................................................ [ 80%]
........................................................................ [ 88%]
.....................s.................................................. [ 96%]
....................................                                     [100%]
898 passed, 2 skipped in 268.08s (0:04:28)
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
- Result: passed (exit 0, 0.7 s)

```text

```

Summary: 6 passed, 0 failed (0 blocking).
