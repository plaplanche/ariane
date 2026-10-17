"""Pushes and pull requests an agent attempted (C19, ADR 0036), read from its shell commands."""

from __future__ import annotations

import shlex
from dataclasses import dataclass

_SEPARATORS = {";", "&&", "||", "|", "&", "|&", "(", ")"}
_SHELLS = {"sh", "bash", "zsh", "dash"}
# Global options of git and gh that take a separate value.
_VALUE_OPTIONS = {"-C", "-c", "--git-dir", "--work-tree", "-R", "--repo"}
_MAX_DEPTH = 3


@dataclass(frozen=True)
class Attempts:
    """Counts of the commands an agent attempted that push or open a pull request."""

    push: int = 0
    pull_request: int = 0

    def __add__(self, other: Attempts) -> Attempts:
        return Attempts(self.push + other.push, self.pull_request + other.pull_request)


class AttemptTally:
    """Counts the attempts in the shell commands of one session."""

    def __init__(self) -> None:
        self.attempts = Attempts()
        self._seen: set[str] = set()

    def add_command(self, command: str, call_id: str) -> None:
        """Count a command once per call id (a streamed message repeats its calls)."""
        if call_id not in self._seen:
            self._seen.add(call_id)
            self.attempts += count(command)


def count(command: str, depth: int = 0) -> Attempts:
    """The attempts in one shell command: `git push` and `gh pr create` as command words.

    A quoted string is one word (`echo "git push"` counts nothing); `git pushd` is another command.
    """
    total = Attempts()
    for words in _simple_commands(command):
        total += _attempt(words, depth)
    return total


def _simple_commands(command: str) -> list[list[str]]:
    lexer = shlex.shlex(command.replace("\n", " ; "), posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    try:
        tokens = list(lexer)
    except ValueError:  # an unbalanced quote: fall back on plain words
        tokens = command.split()
    commands: list[list[str]] = [[]]
    for token in tokens:
        if token in _SEPARATORS:
            commands.append([])
        else:
            commands[-1].append(token)
    return [c for c in commands if c]


def _attempt(words: list[str], depth: int) -> Attempts:
    while words and "=" in words[0] and not words[0].startswith(("=", "-")):
        words = words[1:]  # leading VAR=value assignments
    if not words:
        return Attempts()
    program = words[0].replace("\\", "/").rsplit("/", 1)[-1].removesuffix(".exe")
    rest = _after_options(words[1:])
    if program == "git" and rest[:1] == ["push"]:
        return Attempts(push=1)
    if program == "gh" and rest[:2] == ["pr", "create"]:
        return Attempts(pull_request=1)
    if program in _SHELLS and depth < _MAX_DEPTH and "-c" in words[1:]:
        index = words.index("-c") + 1
        if index < len(words):
            return count(words[index], depth + 1)
    return Attempts()


def _after_options(words: list[str]) -> list[str]:
    """The words after git's or gh's global options."""
    index = 0
    while index < len(words) and words[index].startswith("-"):
        index += 2 if words[index] in _VALUE_OPTIONS else 1
    return words[index:]
