"""The architecture documentation covers every module (ADR 0022)."""

from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def modules_without_file(root: Path) -> list[str]:
    names = {p.stem for p in (root / "src" / "ariane").glob("*.py") if p.stem != "__init__"}
    files = {p.stem for p in (root / "docs" / "architecture" / "modules").glob("*.md")}
    return [f"{n}: no docs/architecture/modules/{n}.md" for n in sorted(names - files)] + [
        f"{n}: no module src/ariane/{n}.py" for n in sorted(files - names)
    ]


def copy_tree(tmp_path: Path) -> Path:
    shutil.copytree(ROOT / "src" / "ariane", tmp_path / "src" / "ariane")
    shutil.copytree(ROOT / "docs" / "architecture", tmp_path / "docs" / "architecture")
    return tmp_path


def test_docs_architecture_every_module_has_a_file() -> None:
    assert modules_without_file(ROOT) == []


def test_docs_architecture_missing_file_fails(tmp_path: Path) -> None:
    root = copy_tree(tmp_path)
    (root / "docs" / "architecture" / "modules" / "git.md").unlink()
    assert modules_without_file(root) == ["git: no docs/architecture/modules/git.md"]


def test_docs_architecture_file_without_module_fails(tmp_path: Path) -> None:
    root = copy_tree(tmp_path)
    (root / "docs" / "architecture" / "modules" / "ghost.md").write_text("# ghost\n")
    assert modules_without_file(root) == ["ghost: no module src/ariane/ghost.py"]


def test_docs_architecture_every_file_has_a_mermaid_diagram() -> None:
    for path in (ROOT / "docs" / "architecture").rglob("*.md"):
        assert "```mermaid" in path.read_text(encoding="utf-8"), path
