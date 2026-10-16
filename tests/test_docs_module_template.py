"""Module files follow the template and name the public API of their module (C25, ADR 0039)."""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SECTIONS = (
    "Public API",
    "Behaviour and errors",
    "Workflow",
    "Code view (C4 level 4)",
    "Collaborations",
    "Reference",
    "Serves",
)
OPTIONAL = {"Reference"}
FENCE = "```"


def public_names(source: str) -> set[str]:
    """Top-level functions, classes and constants defined in the module, without a leading `_`."""
    names: set[str] = set()
    for node in ast.parse(source).body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return {n for n in names if not n.startswith("_")}


def sections(text: str) -> list[tuple[str, str]]:
    """The `## ` sections of a document, outside code fences, as (title, body)."""
    found: list[tuple[str, list[str]]] = []
    fenced = False
    for line in text.splitlines():
        if line.startswith(FENCE):
            fenced = not fenced
        if not fenced and line.startswith("## "):
            found.append((line[3:].strip(), []))
        elif found:
            found[-1][1].append(line)
    return [(title, "\n".join(body)) for title, body in found]


def documented_names(body: str) -> list[str]:
    names = []
    for line in body.splitlines():
        match = re.match(r"\|\s*`(\w+)", line)
        if match:
            names.append(match.group(1))
    return names


def module_file_problems(source: Path, doc: Path) -> list[str]:
    """What is wrong between a module and its module file, each naming the file and the name."""
    problems: list[str] = []
    found = sections(doc.read_text(encoding="utf-8"))
    titles = [t for t, _ in found]
    expected = [s for s in SECTIONS if s in titles or s not in OPTIONAL]
    for title in expected:
        if title not in titles:
            problems.append(f"{doc}: section '{title}' is missing")
    if not problems and titles != expected:
        problems.append(f"{doc}: sections out of order: {titles}, expected {expected}")
    bodies = dict(found)
    if "Public API" in bodies:
        documented = documented_names(bodies["Public API"])
        actual = public_names(source.read_text(encoding="utf-8"))
        problems += [
            f"{doc}: public name '{n}' is missing from Public API"
            for n in sorted(actual - set(documented))
        ]
        problems += [
            f"{doc}: Public API names '{n}', which {source.name} does not define"
            for n in sorted(set(documented) - actual)
        ]
    if (
        "Code view (C4 level 4)" in bodies
        and f"{FENCE}mermaid" not in bodies["Code view (C4 level 4)"]
    ):
        problems.append(f"{doc}: section 'Code view (C4 level 4)' has no Mermaid diagram")
    workflow = bodies.get("Workflow")
    lines = [line for line in (workflow or "").splitlines() if line.strip()]
    if workflow is not None and f"{FENCE}mermaid" not in workflow and len(lines) != 1:
        problems.append(f"{doc}: section 'Workflow' has no Mermaid diagram")
    return problems


GOOD_SOURCE = '''"""m."""
LIMIT = 3
def run(a): ...
class Box: ...
def _private(): ...
'''


def good_doc(
    rows: str = "| `LIMIT` | constant | x |\n| `run(a)` | function | x |\n| `Box` | class | x |",
) -> str:
    diagram = f"{FENCE}mermaid\nflowchart TD\n  a --> b\n{FENCE}\n"
    parts = {
        "Public API": f"| Name | Kind | What it does |\n| --- | --- | --- |\n{rows}\n",
        "Behaviour and errors": "- none\n",
        "Workflow": diagram,
        "Code view (C4 level 4)": diagram.replace("flowchart TD", "classDiagram"),
        "Collaborations": "generated\n",
        "Serves": "C25\n",
    }
    return "# Module `ariane.m`\n\npurpose\n\n" + "".join(
        f"## {t}\n\n{b}\n" for t, b in parts.items()
    )


def write(tmp_path: Path, doc: str) -> tuple[Path, Path]:
    source = tmp_path / "m.py"
    source.write_text(GOOD_SOURCE, encoding="utf-8")
    path = tmp_path / "m.md"
    path.write_text(doc, encoding="utf-8")
    return source, path


def test_c25_module_template_accepts_a_conforming_file(tmp_path: Path) -> None:
    assert module_file_problems(*write(tmp_path, good_doc())) == []


def test_c25_module_template_reports_a_missing_public_name(tmp_path: Path) -> None:
    source, doc = write(tmp_path, good_doc("| `LIMIT` | constant | x |\n| `Box` | class | x |"))
    assert module_file_problems(source, doc) == [
        f"{doc}: public name 'run' is missing from Public API"
    ]


def test_c25_module_template_reports_a_name_the_module_does_not_define(tmp_path: Path) -> None:
    rows = (
        "| `LIMIT` | constant | x |\n| `run(a)` | function | x |\n"
        "| `Box` | class | x |\n| `ghost()` | function | x |"
    )
    source, doc = write(tmp_path, good_doc(rows))
    assert module_file_problems(source, doc) == [
        f"{doc}: Public API names 'ghost', which m.py does not define"
    ]


def test_c25_module_template_reports_a_missing_section(tmp_path: Path) -> None:
    source, doc = write(tmp_path, good_doc().replace("## Behaviour and errors", "## Notes"))
    assert module_file_problems(source, doc) == [
        f"{doc}: section 'Behaviour and errors' is missing"
    ]


def test_c25_module_template_reports_a_misplaced_section(tmp_path: Path) -> None:
    text = (
        good_doc()
        .replace("## Serves", "## Reference\n\nr\n\n## Serves")
        .replace("## Workflow", "## Zed")
    )
    text = text.replace("## Zed", "## Workflow")
    swapped = (
        text.replace("## Collaborations", "## Tmp")
        .replace("## Serves", "## Collaborations")
        .replace("## Tmp", "## Serves")
    )
    source, doc = write(tmp_path, swapped)
    problems = module_file_problems(source, doc)
    assert len(problems) == 1
    assert problems[0].startswith(f"{doc}: sections out of order")


def test_c25_module_template_reports_a_section_without_its_diagram(tmp_path: Path) -> None:
    text = (
        good_doc()
        .replace("classDiagram", "classDiagram_")
        .replace(f"{FENCE}mermaid\nclassDiagram_", "```text\nclassDiagram_")
    )
    source, doc = write(tmp_path, text)
    assert module_file_problems(source, doc) == [
        f"{doc}: section 'Code view (C4 level 4)' has no Mermaid diagram"
    ]
    source, doc = write(
        tmp_path,
        good_doc()
        .replace("flowchart TD", "x")
        .replace(f"{FENCE}mermaid\nx\n  a --> b\n{FENCE}", "two\nlines"),
    )
    assert module_file_problems(source, doc) == [
        f"{doc}: section 'Workflow' has no Mermaid diagram"
    ]


def test_c25_module_template_allows_a_one_line_workflow(tmp_path: Path) -> None:
    text = good_doc().replace(
        f"{FENCE}mermaid\nflowchart TD\n  a --> b\n{FENCE}", "No behaviour of its own."
    )
    assert module_file_problems(*write(tmp_path, text)) == []


def test_c25_module_template_every_module_file_passes() -> None:
    sources = sorted((ROOT / "src" / "ariane").glob("*.py"))
    modules = [p for p in sources if p.stem != "__init__"]
    assert len(modules) >= 28
    problems: list[str] = []
    for source in modules:
        doc = ROOT / "docs" / "architecture" / "modules" / f"{source.stem}.md"
        if not doc.is_file():
            problems.append(f"{doc}: no module file for {source.name}")
            continue
        problems += module_file_problems(source, doc)
    assert problems == []
