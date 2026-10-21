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


_SEGMENT = "segment"  # any character but `/` (a step of `*` or `?`)
_ANY = "any"  # any character (a step of `**`)


def overlap(first: str, second: str) -> bool:
    """Whether some path matches both globs (a literal path is a glob without wildcards): a
    walk of the pairs of states of their two automata, from both starts to both ends."""
    a, b = _Automaton(first), _Automaton(second)
    seen: set[tuple[int, int]] = set()
    todo = [(0, 0)]
    while todo:
        pair = todo.pop()
        if pair in seen:
            continue
        seen.add(pair)
        i, j = pair
        if i == a.end and j == b.end:
            return True
        todo += [(k, j) for k in a.empty[i]] + [(i, k) for k in b.empty[j]]
        todo += [(ka, kb) for x, ka in a.steps[i] for y, kb in b.steps[j] if _meet(x, y)]
    return False


def _meet(x: str, y: str) -> bool:
    """Whether one character can take both steps `x` and `y`."""
    if _ANY in (x, y):
        return True
    if x == _SEGMENT:
        return y != "/"
    return x != "/" if y == _SEGMENT else x == y


class _Automaton:
    """The states of `glob_regex(glob)`: `steps[i]` the characters (one character, `_SEGMENT`
    or `_ANY`) leading from state `i` to another, `empty[i]` the states it reaches without
    one; state 0 is the start, `end` the end."""

    def __init__(self, glob: str) -> None:
        self.steps: list[list[tuple[str, int]]] = [[]]
        self.empty: list[list[int]] = [[]]
        here, i = 0, 0
        while i < len(glob):
            if glob.startswith("**/", i):  # nothing, or any folders: any characters, then `/`
                loop, after = self._state(), self._state()
                self.empty[here] += [loop, after]
                self.steps[loop] += [(_ANY, loop), ("/", after)]
                here, i = after, i + 3
            elif glob.startswith("**", i) or glob[i] == "*":
                width = 2 if glob.startswith("**", i) else 1
                loop = self._state()
                self.empty[here].append(loop)
                self.steps[loop].append((_ANY if width == 2 else _SEGMENT, loop))
                here, i = loop, i + width
            else:
                after = self._state()
                self.steps[here].append((_SEGMENT if glob[i] == "?" else glob[i], after))
                here, i = after, i + 1
        self.end = here

    def _state(self) -> int:
        self.steps.append([])
        self.empty.append([])
        return len(self.steps) - 1
