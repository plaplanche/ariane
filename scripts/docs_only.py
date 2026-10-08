"""Print whether every changed path (one per line on standard input) is documentation."""

from __future__ import annotations

import sys
from collections.abc import Iterable


def is_docs_path(path: str) -> bool:
    path = path.strip().replace("\\", "/")
    if path.startswith("docs/"):
        return True
    return path.endswith(".md") and not path.startswith("work/")


def is_docs_only(paths: Iterable[str]) -> bool:
    cleaned = [path for path in (line.strip() for line in paths) if path]
    return bool(cleaned) and all(is_docs_path(path) for path in cleaned)


def main() -> int:
    print(f"docs_only={'true' if is_docs_only(sys.stdin) else 'false'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
