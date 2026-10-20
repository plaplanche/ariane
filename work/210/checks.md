# Checks

Risk tier: high: no `[checks_policy]`.

Replayed by Ariane on commit `97eaf20110cce408ae3ceb738637801382e6970e`.

Each check was replayed in its own clean working tree at `97eaf20110cce408ae3ceb738637801382e6970e`, after the setup.

| Check | Blocking | Result | Duration |
| --- | --- | --- | --- |
| lint | yes | pass | 0.1 s |
| format | yes | pass | 0.1 s |
| types | yes | pass | 6.6 s |
| tests | yes | pass | 180.5 s |
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
- Result: passed (exit 0, 0.1 s)

```text
730 files already formatted
```

## types

- Command: `uv run mypy`
- Blocking: yes
- Result: passed (exit 0, 6.6 s)

```text
Success: no issues found in 115 source files
```

## tests

- Command: `uv run pytest -q`
- Blocking: yes
- Result: passed (exit 0, 180.5 s)

```text
bringing up nodes...
bringing up nodes...

........................................................................ [  7%]
........................................................................ [ 15%]
........................................................................ [ 23%]
........................................................................ [ 31%]
........................................................................ [ 39%]
......................s................................................. [ 46%]
........................................................................ [ 54%]
........................................................................ [ 62%]
........................................................................ [ 70%]
........................................................................ [ 78%]
........................................................................ [ 86%]
......................................s................................. [ 93%]
........................................................                 [100%]
918 passed, 2 skipped in 179.10s (0:02:59)
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
