"""Platform requirements for subprocesses: UTF-8, PATH resolution, process-tree timeouts."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

from ariane import process

from conftest import PY

GRANDCHILD = """
import subprocess, sys
child = (
    "import time, pathlib\\n"
    "p = pathlib.Path(r'{beat}')\\n"
    "while True:\\n"
    "    p.write_text(str(time.time()))\\n"
    "    time.sleep(0.1)\\n"
)
subprocess.Popen([sys.executable, '-c', child])
import time
time.sleep(60)
"""


def test_process_output_is_utf8_and_invalid_bytes_are_replaced(tmp_path: Path) -> None:
    code = "import sys; sys.stdout.buffer.write('é→ ok '.encode('utf-8') + b'\\xff\\xfe end')"
    done = process.run([PY, "-c", code], cwd=tmp_path)
    assert done.ok
    assert done.stdout.startswith("é→ ok ")
    assert "�" in done.stdout and done.stdout.endswith(" end")


def test_process_stderr_can_be_merged_or_kept_apart(tmp_path: Path) -> None:
    code = "import sys; print('out'); print('err', file=sys.stderr); sys.exit(4)"
    apart = process.run([PY, "-c", code], cwd=tmp_path)
    assert (apart.returncode, apart.stdout, apart.stderr) == (4, "out\n", "err\n")
    assert apart.output == "out\nerr\n"
    merged = process.run([PY, "-c", code], cwd=tmp_path, merge_stderr=True)
    assert "out" in merged.stdout and "err" in merged.stdout


def test_process_input_text_reaches_standard_input(tmp_path: Path) -> None:
    code = "import sys; print(sys.stdin.read().upper())"
    assert process.run([PY, "-c", code], cwd=tmp_path, input_text="ça va").stdout == "ÇA VA\n"


def test_process_unknown_executable_is_reported_by_name(tmp_path: Path) -> None:
    with pytest.raises(process.CommandNotFoundError, match="no-such-tool-for-ariane"):
        process.run(["no-such-tool-for-ariane"], cwd=tmp_path)


def _wait_for(path: Path, seconds: float = 20) -> None:
    deadline = time.monotonic() + seconds
    while not path.exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    assert path.exists(), f"{path} never appeared"


def _assert_stopped(beat: Path) -> None:
    """The heartbeat file stops changing: whatever wrote it is dead."""
    time.sleep(0.5)
    last = beat.read_text()
    time.sleep(1.5)
    assert beat.read_text() == last, "a descendant survived"


def test_process_timeout_kills_the_whole_tree(tmp_path: Path) -> None:
    beat = tmp_path / "beat.txt"
    done = process.run([PY, "-c", GRANDCHILD.format(beat=beat)], cwd=tmp_path, timeout_s=5)
    assert done.timed_out and done.returncode is None and not done.ok
    assert done.duration_s < 30
    _wait_for(beat)
    _assert_stopped(beat)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX process groups")
def test_process_background_children_do_not_outlive_a_normal_exit(tmp_path: Path) -> None:
    beat = tmp_path / "beat.txt"
    code = GRANDCHILD.format(beat=beat).replace("time.sleep(60)", "time.sleep(1)")
    done = process.run([PY, "-c", code], cwd=tmp_path, timeout_s=30)
    assert done.ok and not done.timed_out
    assert done.duration_s < 15, "a background child held the output open"
    _wait_for(beat)
    _assert_stopped(beat)


def test_process_resolution_ignores_relative_path_entries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    name = "ariane-shadow-tool"
    script = tmp_path / (name + (".cmd" if sys.platform == "win32" else ""))
    script.write_text(
        "@echo shadow\r\n" if sys.platform == "win32" else "#!/bin/sh\n", encoding="utf-8"
    )
    script.chmod(0o755)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(process.CommandNotFoundError):
        process.resolve(name, {"PATH": "." + os.pathsep + "relative", "PATHEXT": ".CMD"})
    found = process.resolve(name, {"PATH": str(tmp_path), "PATHEXT": ".CMD"})
    assert Path(found).resolve() == script.resolve()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows .cmd shims")
def test_process_resolves_windows_cmd_shims_through_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "ariane-shim.cmd").write_text("@echo shim says %1\r\n", encoding="utf-8")
    monkeypatch.setenv("PATH", f"{tmp_path};{os.environ['PATH']}")
    done = process.run(["ariane-shim", "hello"], cwd=tmp_path)
    assert done.ok and "shim says hello" in done.stdout
