"""The 600-line limit on Ariane's own source (maintainability requirement)."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def load_script() -> ModuleType:
    path = Path(__file__).resolve().parent.parent / "scripts" / "check_file_length.py"
    spec = importlib.util.spec_from_file_location("check_file_length", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_source_file_over_the_limit_is_reported_and_one_at_the_limit_is_not(
    tmp_path: Path,
) -> None:
    script = load_script()
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "at_limit.py").write_text("x = 1\n" * 600, encoding="utf-8")
    (tmp_path / "src" / "over.py").write_text("x = 1\n" * 601, encoding="utf-8")
    (tmp_path / "work").mkdir()
    (tmp_path / "work" / "journal.md").write_text("line\n" * 5000, encoding="utf-8")
    found = script.too_long(tmp_path)
    assert [(path.as_posix(), lines) for path, lines in found] == [("src/over.py", 601)]
