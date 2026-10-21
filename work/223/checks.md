# Checks

Risk tier: high: no `[checks_policy]`.

Replayed by Ariane on commit `5631f94e7ad56130a02071122a53ef2d05e44d5b`.

Each check was replayed in its own clean working tree at `5631f94e7ad56130a02071122a53ef2d05e44d5b`, after the setup.

| Check | Blocking | Result | Duration |
| --- | --- | --- | --- |
| lint | yes | pass | 0.1 s |
| format | yes | pass | 0.1 s |
| types | yes | pass | 4.0 s |
| tests | yes | pass | 162.8 s |
| file length | yes | pass | 0.1 s |
| docs: references | yes | pass | 0.5 s |

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
794 files already formatted
```

## types

- Command: `uv run mypy`
- Blocking: yes
- Result: passed (exit 0, 4.0 s)

```text
Success: no issues found in 133 source files
```

## tests

- Command: `uv run pytest -q`
- Blocking: yes
- Result: passed (exit 0, 162.8 s)

```text
bringing up nodes...
bringing up nodes...

........................................................................ [  6%]
........................................................................ [ 13%]
........................................................................ [ 20%]
..............................................................s......... [ 27%]
........................................................................ [ 34%]
........................................................................ [ 40%]
........................................................................ [ 47%]
........................................................................ [ 54%]
........................................................................ [ 61%]
........................................................................ [ 68%]
........................................................................ [ 75%]
........................................................................ [ 81%]
........................................................................ [ 88%]
........................s............................................... [ 95%]
................................................                         [100%]
1054 passed, 2 skipped in 162.05s (0:02:42)
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
- Result: passed (exit 0, 0.5 s)

```text

```

Summary: 6 passed, 0 failed (0 blocking).
