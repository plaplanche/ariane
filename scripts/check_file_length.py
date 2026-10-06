"""Fail when a source file of Ariane exceeds the length limit (maintainability requirement)."""

from __future__ import annotations

import sys
from pathlib import Path

LIMIT = 600
ROOTS = ("src", "tests", "scripts")
SUFFIXES = {".py", ".md", ".toml", ".json", ".ps1", ".sh", ".txt"}


def too_long(root: Path, limit: int = LIMIT) -> list[tuple[Path, int]]:
    found = []
    for top in ROOTS:
        if not (root / top).is_dir():
            continue
        for path in sorted((root / top).rglob("*")):
            if path.is_file() and path.suffix in SUFFIXES and "__pycache__" not in path.parts:
                lines = len(path.read_text(encoding="utf-8", errors="replace").splitlines())
                if lines > limit:
                    found.append((path.relative_to(root), lines))
    return found


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    offenders = too_long(root)
    for path, lines in offenders:
        print(f"{path.as_posix()}: {lines} lines (limit {LIMIT})")
    if offenders:
        return 1
    print(f"file length OK: no file over {LIMIT} lines under {', '.join(ROOTS)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
