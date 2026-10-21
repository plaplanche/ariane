"""ADR numbers stay unique when tickets run in parallel (C25, CLAUDE.md rule 2)."""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parent.parent
ADR = ROOT / "docs" / "adr"
DOCS_ONLY = ROOT / "scripts" / "docs_only.py"
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
NAME = re.compile(r"^(\d{4})-")


def adr_problems(folder: Path) -> list[str]:
    """Files of `folder` that share a four-digit number or are misnamed (the README excepted)."""
    problems: list[str] = []
    by_number: dict[str, list[str]] = {}
    for path in sorted(folder.iterdir()):
        if not path.is_file() or path.name == "README.md":
            continue
        match = NAME.match(path.name)
        if match is None:
            problems.append(f"{path.name}: does not start with four digits and a dash")
            continue
        by_number.setdefault(match.group(1), []).append(path.name)
    for number, names in sorted(by_number.items()):
        if len(names) > 1:
            problems.append(f"ADR number {number} is shared by {', '.join(names)}")
    return problems


def test_c25_adr_numbers_repository_unique() -> None:
    assert adr_problems(ADR) == []


def test_c25_adr_numbers_collision_names_both(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# ADRs\n", encoding="utf-8")
    (tmp_path / "0058-earlier.md").write_text("# 0058\n", encoding="utf-8")
    (tmp_path / "0059-review-history.md").write_text("# 0059\n", encoding="utf-8")
    (tmp_path / "0059-next-ticket.md").write_text("# 0059\n", encoding="utf-8")
    problems = adr_problems(tmp_path)
    assert problems == ["ADR number 0059 is shared by 0059-next-ticket.md, 0059-review-history.md"]


def test_c25_adr_numbers_misnamed_file(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# ADRs\n", encoding="utf-8")
    (tmp_path / "0001-fine.md").write_text("# 0001\n", encoding="utf-8")
    (tmp_path / "59-short.md").write_text("# 59\n", encoding="utf-8")
    (tmp_path / "notes.md").write_text("notes\n", encoding="utf-8")
    problems = adr_problems(tmp_path)
    assert problems == [
        "59-short.md: does not start with four digits and a dash",
        "notes.md: does not start with four digits and a dash",
    ]


def load_docs_only() -> ModuleType:
    spec = importlib.util.spec_from_file_location("docs_only", DOCS_ONLY)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_c25_adr_numbers_adr_pull_request_runs_the_tests() -> None:
    # CI skips pytest for a documentation-only pull request; one that adds an ADR is not one,
    # so its merge with the base runs this check (ADR 0061).
    docs_only = load_docs_only()
    assert not docs_only.is_docs_only(["docs/adr/0059-second.md"])
    assert not docs_only.is_docs_only(["docs/adr/0059-second.md", "README.md"])
    assert not docs_only.is_docs_only(["docs\\adr\\0059-second.md"])
    assert docs_only.is_docs_only(["docs/adr/README.md", "docs/architecture/1-context.md"])


def test_c25_adr_numbers_ci_tests_step_runs_this_file() -> None:
    lines = WORKFLOW.read_text(encoding="utf-8").splitlines()
    step = lines.index("      - name: Tests")
    assert lines[step + 1].strip() == "if: steps.docs.outputs.docs_only != 'true'"
    assert lines[step + 2].strip().startswith("run: uv run pytest ")
    assert " -k " not in lines[step + 2] and " tests/" not in lines[step + 2]
