"""Path globs (C9, C22, ADR 0056): the rules of every glob in `ariane.toml`."""

from __future__ import annotations

import re
from collections.abc import Sequence


def matching_paths(globs: Sequence[str], paths: Sequence[str]) -> list[str]:
    """The `paths` that match at least one of the `globs`."""
    regexes = [glob_regex(g) for g in globs]
    return [p for p in paths if any(r.fullmatch(p) for r in regexes)]


def is_glob(text: str) -> bool:
    """Whether `text` holds a wildcard (`*` or `?`), rather than naming one path."""
    return "*" in text or "?" in text


def glob_regex(glob: str) -> re.Pattern[str]:
    """`*` and `?` stay within a path segment, `**` crosses segments, `**/` is any folders."""
    out = []
    i = 0
    while i < len(glob):
        if glob.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
            continue
        if glob.startswith("**", i):
            out.append(".*")
            i += 2
            continue
        c = glob[i]
        out.append("[^/]*" if c == "*" else "[^/]" if c == "?" else re.escape(c))
        i += 1
    return re.compile("".join(out), re.DOTALL)  # a line break in a file name is matched too
