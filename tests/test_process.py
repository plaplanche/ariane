"""Platform requirements for subprocesses: UTF-8, PATH resolution, process-tree timeouts."""

from __future__ import annotations

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


def test_process_timeout_kills_the_whole_tree(tmp_path: Path) -> None:
    beat = tmp_path / "beat.txt"
    done = process.run([PY, "-c", GRANDCHILD.format(beat=beat)], cwd=tmp_path, timeout_s=3)
    assert done.timed_out and done.returncode is None and not done.ok
    assert done.duration_s < 30
    time.sleep(0.5)
    last = beat.read_text()
    time.sleep(1.0)
    assert beat.read_text() == last, "the grandchild survived the timeout"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows .cmd shims")
def test_process_resolves_windows_cmd_shims_through_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "ariane-shim.cmd").write_text("@echo shim says %1\r\n", encoding="utf-8")
    monkeypatch.setenv("PATH", f"{tmp_path};{__import__('os').environ['PATH']}")
    done = process.run(["ariane-shim", "hello"], cwd=tmp_path)
    assert done.ok and "shim says hello" in done.stdout
