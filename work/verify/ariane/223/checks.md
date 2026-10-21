# Checks

Risk tier: high: no `[checks_policy]`.

Replayed by Ariane on commit `dde98418743568725f80c2f715cfedad2a77eca3`.

Each check was replayed in its own clean working tree at `dde98418743568725f80c2f715cfedad2a77eca3`, after the setup.

| Check | Blocking | Result | Duration |
| --- | --- | --- | --- |
| lint | yes | pass | 0.2 s |
| format | yes | pass | 0.2 s |
| types | yes | pass | 4.0 s |
| tests | yes | pass | 159.2 s |
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
808 files already formatted
```

## types

- Command: `uv run mypy`
- Blocking: yes
- Result: passed (exit 0, 4.0 s)

```text
Success: no issues found in 135 source files
```

## tests

- Command: `uv run pytest -q`
- Blocking: yes
- Result: passed (exit 0, 159.2 s)

```text
bringing up nodes...
bringing up nodes...

........................................................................ [  6%]
........................................................................ [ 13%]
........................................................................ [ 20%]
........................................................s............... [ 26%]
........................................................................ [ 33%]
........................................................................ [ 40%]
........................................................................ [ 46%]
........................................................................ [ 53%]
........................................................................ [ 60%]
........................................................................ [ 67%]
........................................................................ [ 73%]
........................................................................ [ 80%]
........................................................................ [ 87%]
........................................................................ [ 93%]
...........................s......................................       [100%]
1072 passed, 2 skipped in 158.43s (0:02:38)
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
