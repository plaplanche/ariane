"""Sequence diagrams only draw calls between modules that import each other (C25, ADR 0039)."""

from __future__ import annotations

import re
from pathlib import Path

from test_docs_graph import ARCH, ROOT, load_script

PARTICIPANT = re.compile(r"^\s*(participant|actor) (\w+)(?: as (.+))?$")
ARROW = re.compile(r"^\s*(\w+)\s*(-->>|->>|-->|->|--\)|-\)|--x|-x)\s*[+-]?(\w+)\s*:")


def check_file(
    path: Path, root: Path, modules: set[str], edges: set[tuple[str, str]], seen: list[str]
) -> list[str]:
    problems: list[str] = []
    text = path.read_text(encoding="utf-8")
    for block in re.findall(r"```mermaid\n(sequenceDiagram.*?)```", text, re.S):
        declared: set[str] = set()
        alias: dict[str, str] = {}
        for line in block.splitlines():
            m = PARTICIPANT.match(line)
            if m:
                declared.add(m.group(2))
                label = (m.group(3) or m.group(2)).strip()
                word = re.match(r"\w+", label)
                if m.group(1) == "participant" and word and word.group(0) in modules:
                    alias[m.group(2)] = word.group(0)
        for line in block.splitlines():
            m = ARROW.match(line)
            if not m:
                continue
            where = f"{path.relative_to(root)}: `{line.strip()}`"
            src, kind, dst = m.groups()
            seen.append(line)
            if not {src, dst} <= declared:
                problems.append(f"{where} uses a participant that is not declared")
            elif kind == "-->>":
                continue
            elif kind != "->>":
                problems.append(f"{where} is an unchecked arrow")
            elif src in alias and dst in alias and alias[src] != alias[dst]:
                a, b = alias[src], alias[dst]
                if (a, b) not in edges:
                    problems.append(f"{where} draws {a} -> {b}, but {a} does not import {b}")
    return problems


def run(root: Path, package: Path, seen: list[str] | None = None) -> list[str]:
    script = load_script()
    graph = script.import_graph(package)
    modules = {a for a, _, _ in graph} | {b for _, b, _ in graph}
    modules |= {p.stem for p in package.glob("*.py")}
    edges = {(a, b) for a, b, _ in graph}
    problems: list[str] = []
    seen = [] if seen is None else seen
    for path in sorted(root.rglob("*.md")):
        problems += check_file(path, root, modules, edges, seen)
    return problems


def test_c25_sequences_repository_passes() -> None:
    seen: list[str] = []
    assert run(ARCH, ROOT / "src" / "ariane", seen) == []
    assert len(seen) > 50


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
    assert problems[0].startswith("s.md:")
    assert "B->>C: bad" in problems[0] and "b does not import c" in problems[0]


def test_c25_sequences_actor_target_and_unknown_arrow(tmp_path: Path) -> None:
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "a.py").write_text("")
    (package / "c.py").write_text("")
    docs = tmp_path / "docs" / "sub"
    docs.mkdir(parents=True)
    (docs / "s.md").write_text(
        "```mermaid\nsequenceDiagram\n  actor U as User\n  participant A as a\n"
        "  participant C as c\n  A->>U: to actor\n  A-)C: async\n  A ->> C: spaced\n"
        "  A->>Z: implicit\n```\n"
    )
    problems = run(tmp_path / "docs", package)
    assert len(problems) == 3
    assert all(p.startswith("sub/s.md:") or p.startswith("sub\\s.md:") for p in problems)
    assert "A-)C: async" in problems[0] and "unchecked" in problems[0]
    assert "A ->> C: spaced" in problems[1] and "a does not import c" in problems[1]
    assert "A->>Z: implicit" in problems[2] and "not declared" in problems[2]
