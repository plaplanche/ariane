# Checks

Replayed by Ariane on commit `c069af7c62ed20c0403f5d522bf66a047aa8c744`.

Each check was replayed in its own clean working tree at `c069af7c62ed20c0403f5d522bf66a047aa8c744`, after the setup.

| Check | Blocking | Result | Duration |
| --- | --- | --- | --- |
| lint | yes | pass | 0.2 s |
| format | yes | pass | 0.2 s |
| types | yes | pass | 3.4 s |
| tests | yes | **fail** (exit 1) | 245.5 s |
| file length | yes | pass | 0.2 s |
| docs: references | yes | pass | 0.4 s |

## lint

- Command: `uv run ruff check .`
- Blocking: yes
- Result: passed (exit 0, 0.2 s)

```text
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
All checks passed!
```

## format

- Command: `uv run ruff format --check .`
- Blocking: yes
- Result: passed (exit 0, 0.2 s)

```text
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
557 files already formatted
```

## types

- Command: `uv run mypy`
- Blocking: yes
- Result: passed (exit 0, 3.4 s)

```text
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
Success: no issues found in 89 source files
```

## tests

- Command: `uv run pytest -q`
- Blocking: yes
- Result: failed (exit 1, 245.5 s)

```text
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
........................................................................ [ 11%]
........................................................................ [ 23%]
...................s....F............................................... [ 35%]
........................................................................ [ 47%]
........................................................................ [ 59%]
........................................................................ [ 71%]
........................................................................ [ 83%]
........................s............................................... [ 94%]
...............................                                          [100%]
=================================== FAILURES ===================================
_____ test_c5_budget_stream_the_cap_stops_the_session_and_the_process_tree _____

tmp_path = PosixPath('/tmp/pytest-of-root/pytest-132/test_c5_budget_stream_the_cap_0')

    def test_c5_budget_stream_the_cap_stops_the_session_and_the_process_tree(
        tmp_path: Path,
    ) -> None:
        pidfile = tmp_path / "child.pid"
        result = run_stream(tmp_path, STREAM, max_tokens=6000, pidfile=str(pidfile), end="hang")
        assert result.stop_reason is StopReason.BUDGET
        assert result.summary == "stopped by Ariane at 11564 tokens"
        assert result.cap is not None and "Ariane token cap (6000 tokens)" in result.cap
        pid = int(pidfile.read_text(encoding="utf-8"))
        deadline = time.monotonic() + 5
        while alive(pid) and time.monotonic() < deadline:
            time.sleep(0.1)
>       assert not alive(pid)
E       assert not True
E        +  where True = alive(25752)

tests/test_c5_budget_stream.py:90: AssertionError
=========================== short test summary info ============================
FAILED tests/test_c5_budget_stream.py::test_c5_budget_stream_the_cap_stops_the_session_and_the_process_tree
1 failed, 604 passed, 2 skipped in 244.78s (0:04:04)
```

## file length

- Command: `uv run python scripts/check_file_length.py`
- Blocking: yes
- Result: passed (exit 0, 0.2 s)

```text
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
file length OK: no file over 600 lines under src, tests, scripts
```

## docs: references

- Command: `uv run python scripts/generate_docs.py --check`
- Blocking: yes
- Result: passed (exit 0, 0.4 s)

```text
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
```

Summary: 5 passed, 1 failed (1 blocking).
