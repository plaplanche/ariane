# Checks

Risk tier: high: no `[checks_policy]`.

Replayed by Ariane on commit `14aed46849415033ccb1ac01463dc5cad674cbfb`.

Each check was replayed in its own clean working tree at `14aed46849415033ccb1ac01463dc5cad674cbfb`, after the setup.

| Check | Blocking | Result | Duration |
| --- | --- | --- | --- |
| lint | yes | pass | 0.1 s |
| format | yes | pass | 0.1 s |
| types | yes | pass | 4.2 s |
| tests | yes | **fail** (exit 1) | 149.1 s |
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
747 files already formatted
```

## types

- Command: `uv run mypy`
- Blocking: yes
- Result: passed (exit 0, 4.2 s)

```text
Success: no issues found in 118 source files
```

## tests

- Command: `uv run pytest -q`
- Blocking: yes
- Result: failed (exit 1, 149.1 s)

```text
bringing up nodes...
bringing up nodes...

........................................................................ [  7%]
........................................................................ [ 15%]
........................................................................ [ 22%]
........................................................................ [ 30%]
........................................s............................... [ 37%]
........................................................................ [ 45%]
...............F........................................................ [ 53%]
........................................................................ [ 60%]
........................................................................ [ 68%]
........................................................................ [ 75%]
........................................................................ [ 83%]
.....................................................................s.. [ 91%]
........................................................................ [ 98%]
............                                                             [100%]
=================================== FAILURES ===================================
____ test_c5_pi_a_ticket_is_reviewed_and_delivered_with_the_usage_recorded _____
[gw0] linux -- Python 3.13.16 /home/user/takeover-145.ariane/worktrees/verify-ariane-145-4/.venv/bin/python

project = Project(root=PosixPath('/tmp/pytest-of-root/pytest-381/popen-gw0/test_c5_pi_a_ticket_is_reviewe0/proj'), remote=PosixPath('/tmp/pytest-of-root/pytest-381/popen-gw0/test_c5_pi_a_ticket_is_reviewe0/origin.git'))
tracker = InMemoryTracker(issues={7: Issue(number=7, title='Bump the app version', body='Set app.txt to version 2.', url='memory...ariane/7/work/7/checks.md'}], refuse_statuses=False, pull_states={}, unreachable=False, labels={}, refuse_labels=False)
tmp_path = PosixPath('/tmp/pytest-of-root/pytest-381/popen-gw0/test_c5_pi_a_ticket_is_reviewe0')

    def test_c5_pi_a_ticket_is_reviewed_and_delivered_with_the_usage_recorded(
        project: Project, tracker: InMemoryTracker, tmp_path: Path
    ) -> None:
        outcome = _pi_ticket(project, tracker, tmp_path, _go_stream(tmp_path))
>       assert outcome.exit_code == 0, outcome.line
E       AssertionError: Stopped ticket #7: git commit failed. Next: read the error above and retry.
E       assert 1 == 0
E        +  where 1 = Outcome(exit_code=1, line='Stopped ticket #7: git commit failed. Next: read the error above and retry.', detail='git c... signing operation failed: signing server returned status 502 (155-byte body)\n\nfatal: failed to write commit object').exit_code

tests/test_c5_pi.py:419: AssertionError
------------------------------ Captured log call -------------------------------
ERROR    ariane:logs.py:248 ticket #7: git commit failed
=========================== short test summary info ============================
FAILED tests/test_c5_pi.py::test_c5_pi_a_ticket_is_reviewed_and_delivered_with_the_usage_recorded
1 failed, 945 passed, 2 skipped in 148.19s (0:02:28)
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

Summary: 5 passed, 1 failed (1 blocking).
