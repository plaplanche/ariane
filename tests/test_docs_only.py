"""The documentation-only rule that lets CI skip its heavy steps (ADR 0005)."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "docs_only.py"
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


def load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("docs_only", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_ci_docs_only_docs_paths() -> None:
    assert load_script().is_docs_only(["docs/adr/0005-ci-matrix.md", "docs/learnings/x.txt"])


def test_ci_docs_only_readme_and_claude() -> None:
    assert load_script().is_docs_only(["README.md", "CLAUDE.md"])


def test_ci_docs_only_markdown_under_work_is_not_docs() -> None:
    assert not load_script().is_docs_only(["work/18/ticket.md"])


def test_ci_docs_only_source_among_docs_is_not_docs() -> None:
    assert not load_script().is_docs_only(["docs/a.md", "src/ariane/cli.py"])


def test_ci_docs_only_workflow_is_not_docs() -> None:
    assert not load_script().is_docs_only([".github/workflows/ci.yml"])


def test_ci_docs_only_empty_list_is_not_docs() -> None:
    assert not load_script().is_docs_only([])


def test_ci_docs_only_script_prints_the_decision() -> None:
    def run(text: str) -> str:
        done = subprocess.run(
            [sys.executable, str(SCRIPT)], input=text, capture_output=True, text=True, check=True
        )
        return done.stdout.strip()

    assert run("docs/a.md\nREADME.md\n") == "docs_only=true"
    assert run("") == "docs_only=false"


def test_ci_docs_only_detection_lists_renamed_paths_on_both_sides() -> None:
    """A rename of code into docs must show the old path, or it would skip every check."""
    lines = [
        line for line in WORKFLOW.read_text(encoding="utf-8").splitlines() if "docs_only.py" in line
    ]
    assert lines and all("git diff --name-only --no-renames" in line for line in lines)
