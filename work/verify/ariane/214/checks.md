# Checks

Replayed by Ariane on commit `053a37c4d89f9c1241d197d3e4039ff271e2a577`.

Each check was replayed in its own clean working tree at `053a37c4d89f9c1241d197d3e4039ff271e2a577`, after the setup.

| Check | Blocking | Result | Duration |
| --- | --- | --- | --- |
| lint | yes | pass | 0.2 s |
| format | yes | pass | 0.2 s |
| types | yes | pass | 5.8 s |
| tests | yes | pass | 121.5 s |
| file length | yes | pass | 0.2 s |
| docs: references | yes | pass | 0.5 s |

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
678 files already formatted
```

## types

- Command: `uv run mypy`
- Blocking: yes
- Result: passed (exit 0, 5.8 s)

```text
Success: no issues found in 107 source files
```

## tests

- Command: `uv run pytest -q`
- Blocking: yes
- Result: passed (exit 0, 121.5 s)

```text
bringing up nodes...
bringing up nodes...

........................................................................ [  8%]
........................................................................ [ 17%]
........................................................................ [ 26%]
........................................................................ [ 35%]
.............................s.......................................... [ 44%]
........................................................................ [ 53%]
........................................................................ [ 62%]
........................................................................ [ 71%]
........................................................................ [ 80%]
........................................................................ [ 89%]
............................................................s........... [ 98%]
............                                                             [100%]
802 passed, 2 skipped in 120.64s (0:02:00)
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
- Result: passed (exit 0, 0.5 s)

```text

```

Summary: 6 passed, 0 failed (0 blocking).
