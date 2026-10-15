"""C19: the README tells a second user how to measure Ariane in shadow mode."""

from __future__ import annotations

import re
from pathlib import Path

README = Path(__file__).resolve().parent.parent / "README.md"
HEADING = "## Measure Ariane on your project (shadow mode)"


def section() -> str:
    text = README.read_text(encoding="utf-8")
    assert HEADING in text
    return re.split(r"^## ", text.split(HEADING, 1)[1], maxsplit=1, flags=re.M)[0]


def blocks(language: str) -> list[str]:
    return re.findall(rf"```{language}\n(.*?)```", section(), flags=re.S)


def test_c19_readme_shadow_section_exists() -> None:
    assert "never pushes" in section()
    assert "10 tickets" in section()


def test_c19_readme_shadow_commands_in_bash_and_powershell() -> None:
    for language in ("bash", "powershell"):
        found = blocks(language)
        assert found, language
        for command in ("--shadow", "ariane judge", "ariane report"):
            assert any(command in block for block in found), (language, command)
