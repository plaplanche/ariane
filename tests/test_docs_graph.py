"""The generated import graph and blocks of the architecture documentation (C25, ADR 0039)."""

from __future__ import annotations

import importlib.util
import re
import shutil
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parent.parent
ARCH = ROOT / "docs" / "architecture"


def load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "generate_docs", ROOT / "scripts" / "generate_docs.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


EDGE = re.compile(r"^\s+(\w+) (-->|-\.->) (\w+)$", re.M)


def write_package(base: Path) -> Path:
    package = base / "pkg"
    package.mkdir()
    files = {
        "__init__.py": "from pkg import a\n",
        "a.py": "from pkg import b\nimport os\nimport requests\n",
        "b.py": "def f():\n    from pkg.c import thing\n    return thing\n",
        "c.py": "from . import d\nfrom .a import x\n",
        "d.py": "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    from pkg import a\n",
        "e.py": "import pkg.a\nfrom pkg import b\nfrom pkg import b\n",
    }
    for name, text in files.items():
        (package / name).write_text(text)
    return package


def test_c25_import_graph_finds_every_form_and_ignores_outside_modules(tmp_path: Path) -> None:
    edges = load_script().import_graph(write_package(tmp_path))
    assert edges == [
        ("a", "b", False),
        ("b", "c", False),
        ("c", "a", False),
        ("c", "d", False),
        ("d", "a", True),
        ("e", "a", False),
        ("e", "b", False),
    ]


def test_c25_generated_block_rewrite_keeps_the_rest_byte_identical() -> None:
    script = load_script()
    before, after = "intro\r\n\n  text ", "\n\n## Next\ntail"
    text = f"{before}<!-- generated: x -->\nold\n<!-- end generated -->{after}"
    new = script.replace_block(text, "x", "new")
    assert new == f"{before}<!-- generated: x -->\nnew\n<!-- end generated -->{after}"


def test_c25_generated_block_check_names_a_differing_file_and_a_missing_marker(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    script = load_script()
    shutil.copytree(ROOT / "src" / "ariane", tmp_path / "src" / "ariane")
    shutil.copytree(ARCH, tmp_path / "docs" / "architecture")
    script.main([], root=tmp_path)
    assert script.main(["--check"], root=tmp_path) == 0
    modules = tmp_path / "docs" / "architecture" / "modules"
    git = modules / "git.md"
    git.write_text(git.read_text().replace("git --> process", "git --> nothing"))
    cli = modules / "cli.md"
    cli.write_text(cli.read_text().replace("<!-- generated: collaborations -->", ""))
    capsys.readouterr()
    assert script.main(["--check"], root=tmp_path) == 1
    out = capsys.readouterr().out
    assert "docs/architecture/modules/git.md: differs" in out
    assert "docs/architecture/modules/cli.md: no `<!-- generated: collaborations -->`" in out


def drawn(text: str) -> set[tuple[str, str, bool]]:
    return {(a, b, arrow == "-.->") for a, arrow, b in EDGE.findall(text)}


def test_c25_architecture_graph_docs_equal_the_computed_graph() -> None:
    script = load_script()
    edges = script.import_graph(ROOT / "src" / "ariane")
    assert drawn(
        (ARCH / "3-components.md").read_text(encoding="utf-8").split("## `ariane")[0]
    ) == set(edges)
    for path in (ARCH / "modules").glob("*.md"):
        text = path.read_text(encoding="utf-8")
        block = text.split("<!-- generated: collaborations -->")[1].split("<!-- end generated")[0]
        assert drawn(block) == {e for e in edges if path.stem in e[:2]}, path


def test_c25_architecture_graph_readme_lists_every_module() -> None:
    text = (ARCH / "README.md").read_text(encoding="utf-8")
    for path in (ROOT / "src" / "ariane").glob("*.py"):
        if path.stem != "__init__":
            assert f"- [`{path.stem}`](modules/{path.stem}.md)" in text
