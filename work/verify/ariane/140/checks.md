# Checks

Replayed by Ariane on commit `68a4e2dbec0ddf8226abde55ca5a0714fcd61614`.

Each check was replayed in its own clean working tree at `68a4e2dbec0ddf8226abde55ca5a0714fcd61614`, after the setup.

| Check | Blocking | Result | Duration |
| --- | --- | --- | --- |
| lint | yes | pass | 0.1 s |
| format | yes | pass | 0.1 s |
| types | yes | pass | 3.5 s |
| tests | yes | pass | 381.5 s |
| file length | yes | pass | 0.1 s |
| docs: references | yes | pass | 0.6 s |

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
615 files already formatted
```

## types

- Command: `uv run mypy`
- Blocking: yes
- Result: passed (exit 0, 3.5 s)

```text
Success: no issues found in 97 source files
```

## tests

- Command: `uv run pytest -q`
- Blocking: yes
- Result: passed (exit 0, 381.5 s)

```text
........................................................................ [ 10%]
........................................................................ [ 20%]
........................................................................ [ 30%]
.............s.......................................................... [ 40%]
........................................................................ [ 50%]
........................................................................ [ 60%]
........................................................................ [ 70%]
........................................................................ [ 80%]
.........................................................s.............. [ 91%]
................................................................         [100%]
710 passed, 2 skipped in 380.89s (0:06:20)
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
- Result: passed (exit 0, 0.6 s)

```text

```

Summary: 6 passed, 0 failed (0 blocking).
