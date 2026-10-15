"""Sequence diagrams only draw calls between modules that import each other (C25, ADR 0039)."""

from __future__ import annotations

import re
from pathlib import Path

from test_docs_graph import ARCH, ROOT, load_script

PARTICIPANT = re.compile(r"^\s*participant (\w+)(?: as (.+))?$")
ARROW = re.compile(r"^\s*(\w+)->>(\w+):")


def check_file(path: Path, modules: set[str], edges: set[tuple[str, str]]) -> list[str]:
    problems: list[str] = []
    text = path.read_text(encoding="utf-8")
    for block in re.findall(r"```mermaid\n(sequenceDiagram.*?)```", text, re.S):
        alias: dict[str, str] = {}
        for line in block.splitlines():
            m = PARTICIPANT.match(line)
            if m:
                label = (m.group(2) or m.group(1)).strip()
                word = re.match(r"\w+", label)
                if word and word.group(0) in modules:
                    alias[m.group(1)] = word.group(0)
        for line in block.splitlines():
            m = ARROW.match(line)
            if not m or m.group(1) not in alias or m.group(2) not in alias:
                continue
            a, b = alias[m.group(1)], alias[m.group(2)]
            if a != b and (a, b) not in edges:
                problems.append(
                    f"{path.name}: `{line.strip()}` draws {a} -> {b}, but {a} does not import {b}"
                )
    return problems


def run(root: Path, package: Path) -> list[str]:
    script = load_script()
    graph = script.import_graph(package)
    modules = {a for a, _, _ in graph} | {b for _, b, _ in graph}
    modules |= {p.stem for p in package.glob("*.py")}
    edges = {(a, b) for a, b, _ in graph}
    problems: list[str] = []
    for path in sorted(root.rglob("*.md")):
        problems += check_file(path, modules, edges)
    return problems


def test_c25_sequences_repository_passes() -> None:
    assert run(ARCH, ROOT / "src" / "ariane") == []


def test_c25_sequences_report_missing_import(tmp_path: Path) -> None:
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "a.py").write_text("from pkg import b\n")
    (package / "b.py").write_text("")
    (package / "c.py").write_text("")
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "s.md").write_text(
        "```mermaid\nsequenceDiagram\n  actor U as User\n  participant A as a\n"
        "  participant B as b (impl)\n  participant C as c\n"
        "  U->>A: go\n  A->>B: ok\n  B-->>A: return\n  B->>B: self\n  B->>C: bad\n```\n"
    )
    problems = run(docs, package)
    assert len(problems) == 1
    assert (
        "s.md" in problems[0]
        and "B->>C: bad" in problems[0]
        and "b does not import c" in problems[0]
    )
