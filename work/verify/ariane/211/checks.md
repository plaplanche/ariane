# Checks

Risk tier: high: no `[checks_policy]`.

Replayed by Ariane on commit `98006d96ee5c7d2ab7e149a66ec22c0254e2e0cf`.

Each check was replayed in its own clean working tree at `98006d96ee5c7d2ab7e149a66ec22c0254e2e0cf`, after the setup.

| Check | Blocking | Result | Duration |
| --- | --- | --- | --- |
| lint | yes | pass | 0.2 s |
| format | yes | pass | 0.3 s |
| types | yes | pass | 6.2 s |
| types (Windows) | yes | pass | 6.3 s |
| tests | yes | pass | 264.2 s |
| file length | yes | pass | 0.2 s |
| docs: references | yes | pass | 0.7 s |

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
- Result: passed (exit 0, 0.3 s)

```text
830 files already formatted
```

## types

- Command: `uv run mypy`
- Blocking: yes
- Result: passed (exit 0, 6.2 s)

```text
Success: no issues found in 138 source files
```

## types (Windows)

- Command: `uv run mypy --platform win32`
- Blocking: yes
- Result: passed (exit 0, 6.3 s)

```text
Success: no issues found in 138 source files
```

## tests

- Command: `uv run pytest -q`
- Blocking: yes
- Result: passed (exit 0, 264.2 s)

```text
bringing up nodes...
bringing up nodes...

........................................................................ [  6%]
........................................................................ [ 13%]
........................................................................ [ 19%]
.....................................s.................................. [ 26%]
........................................................................ [ 32%]
........................................................................ [ 39%]
........................................................................ [ 45%]
........................................................................ [ 52%]
........................................................................ [ 58%]
........................................................................ [ 65%]
........................................................................ [ 72%]
........................................................................ [ 78%]
........................................................................ [ 85%]
...............................................................s........ [ 91%]
........................................................................ [ 98%]
....................                                                     [100%]
1098 passed, 2 skipped in 262.95s (0:04:22)
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
- Result: passed (exit 0, 0.7 s)

```text

```

Summary: 7 passed, 0 failed (0 blocking).
