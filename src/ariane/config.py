"""Load and validate `ariane.toml` (C22). Every error names the faulty key."""

from __future__ import annotations

import ipaddress
import math
import os
import re
import tomllib
import urllib.parse
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ariane.config_schema import OPENCODE, OPENCODE_TOOLS, RUNTIMES, SCHEMA

__all__ = ["OPENCODE", "SCHEMA"]

CONFIG_FILE = "ariane.toml"
CONFIG_ENV = "ARIANE_CONFIG"


class ConfigError(Exception):
    """The configuration is missing or invalid."""


@dataclass(frozen=True)
class TrackerConfig:
    kind: str
    repository: str
    token_env: str
    api_url: str


@dataclass(frozen=True)
class AgentConfig:
    runtime: str
    model: str
    tools: tuple[str, ...]
    max_budget_usd: float
    timeout_minutes: float
    max_tokens: int | None = None


@dataclass(frozen=True)
class CheckConfig:
    name: str
    command: tuple[str, ...]
    blocking: bool
    timeout_minutes: float


@dataclass(frozen=True)
class DoneItem:
    """One item of the definition of done: a declared check, or a sentence."""

    check: str | None = None
    text: str | None = None

    @property
    def label(self) -> str:
        return f"check {self.check} passes" if self.check is not None else str(self.text)


@dataclass(frozen=True)
class DocMapEntry:
    """Source files (a glob) and the documents that cover them."""

    source: str
    docs: tuple[str, ...]

    def documents_for(self, path: str) -> tuple[str, ...]:
        """The documents covering `path`, `{stem}` expanded; none if the glob does not match."""
        if not _glob_regex(self.source).fullmatch(path):
            return ()
        stem = path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        return tuple(d.replace("{stem}", stem) for d in self.docs)


@dataclass(frozen=True)
class GeneratedDoc:
    name: str
    check: tuple[str, ...]


@dataclass(frozen=True)
class Documentation:
    paths: tuple[str, ...] = ()
    map: tuple[DocMapEntry, ...] = ()
    generated: tuple[GeneratedDoc, ...] = ()

    def documents_for(self, path: str) -> list[str]:
        found: list[str] = []
        for entry in self.map:
            found += [d for d in entry.documents_for(path) if d not in found]
        return found

    def not_updated(self, changed: Sequence[str]) -> list[str]:
        """Documents covering the `changed` files that are not themselves changed (a folder
        counts as changed when a file under it is)."""
        touched = set(changed)
        missing: list[str] = []
        for path in changed:
            for doc in self.documents_for(path):
                folder = doc.rstrip("/") + "/"
                under = any(t.startswith(folder) for t in touched)
                if doc not in touched and doc not in missing and not under:
                    missing.append(doc)
        return missing

    def checks(self) -> tuple[CheckConfig, ...]:
        """The generated documents' commands as blocking checks named `docs: <name>`."""
        return tuple(CheckConfig(f"docs: {g.name}", g.check, True, 15) for g in self.generated)


NO_DOCUMENTATION = Documentation()


def _glob_regex(glob: str) -> re.Pattern[str]:
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
    return re.compile("".join(out))


DEFAULT_DEFINITION_OF_DONE = (
    DoneItem(text="Every blocking check passes."),
    DoneItem(text="The change is covered by tests that fail without it."),
    DoneItem(text="The documentation the change affects is updated (C25)."),
)


@dataclass(frozen=True)
class Config:
    base_branch: str
    setup: tuple[str, ...] | None
    tracker: TrackerConfig
    implementer: AgentConfig
    reviewer: AgentConfig
    checks: tuple[CheckConfig, ...]
    definition_of_done: tuple[DoneItem, ...] = DEFAULT_DEFINITION_OF_DONE
    documentation: Documentation = NO_DOCUMENTATION


def load(repo_root: Path, environ: Mapping[str, str] | None = None) -> Config:
    """Read `ariane.toml` at the repository root, or the file `ARIANE_CONFIG` names (C22)."""
    chosen = (os.environ if environ is None else environ).get(CONFIG_ENV, "")
    path = repo_root / chosen if chosen else repo_root / CONFIG_FILE
    shown = f"{CONFIG_ENV} ({chosen})" if chosen else CONFIG_FILE
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ConfigError(f"{shown}: file not found in {repo_root}") from None
    except OSError as exc:
        raise ConfigError(f"{shown}: cannot be read: {exc}") from None
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{shown}: not valid TOML: {exc}") from None
    try:
        return parse(data)
    except ConfigError as exc:
        if not chosen:
            raise
        raise ConfigError(str(exc).replace(f"{CONFIG_FILE}:", f"{shown}:", 1)) from None


def parse(data: dict[str, Any]) -> Config:
    _only(
        data, "", {"project", "tracker", "agents", "checks", "definition_of_done", "documentation"}
    )
    project = _table(data, "project")
    _only(project, "project", {"base_branch", "setup"})
    tracker = _table(data, "tracker")
    _only(tracker, "tracker", {"kind", "repository", "token_env", "api_url"})
    agents = _table(data, "agents")
    _only(agents, "agents", {"implementer", "reviewer"})
    implementer = _agent(agents, "implementer")
    reviewer = _agent(agents, "reviewer")
    if reviewer.model == implementer.model:
        raise ConfigError(
            f"{CONFIG_FILE}: agents.reviewer.model: must differ from agents.implementer.model"
            f" ({reviewer.model!r}); the review is by a different model (C10)"
        )
    raw_checks = data.get("checks")
    if not isinstance(raw_checks, list) or not raw_checks:
        raise ConfigError(f"{CONFIG_FILE}: checks: at least one [[checks]] table is required")

    kind = _str(tracker, "kind", "tracker.")
    if kind != "github":
        raise ConfigError(f"{CONFIG_FILE}: tracker.kind: unsupported value {kind!r} (github)")
    repository = _str(tracker, "repository", "tracker.")
    if repository.count("/") != 1 or "" in repository.split("/"):
        raise ConfigError(f"{CONFIG_FILE}: tracker.repository: expected owner/name")
    base_branch = _str(project, "base_branch", "project.")
    if base_branch.startswith("-") or any(c.isspace() or c in "~^:?*[\\" for c in base_branch):
        raise ConfigError(f"{CONFIG_FILE}: project.base_branch: not a valid branch name")
    api_url = _str(tracker, "api_url", "tracker.", "https://api.github.com").rstrip("/")
    if not _safe_api_url(api_url):
        raise ConfigError(
            f"{CONFIG_FILE}: tracker.api_url: expected an https:// URL (the token is sent there)"
        )

    setup = None
    if "setup" in project:
        setup = _str_list(project, "setup", "project.")
    checks = _checks(raw_checks)
    documentation = _documentation(data)
    names = {c.name for c in (*checks, *documentation.checks())}
    return Config(
        base_branch=base_branch,
        setup=setup,
        tracker=TrackerConfig(
            kind=kind,
            repository=repository,
            token_env=_str(tracker, "token_env", "tracker."),
            api_url=api_url,
        ),
        implementer=implementer,
        reviewer=reviewer,
        checks=checks,
        definition_of_done=_definition_of_done(data, names),
        documentation=documentation,
    )


REVIEWER_FORBIDDEN_TOOLS = ("Write", "Edit", "NotebookEdit", "Bash")


def _agent(agents: dict[str, Any], role: str) -> AgentConfig:
    where = f"agents.{role}"
    table = _table(agents, role, "agents.")
    _only(
        table,
        where,
        {"runtime", "model", "tools", "max_budget_usd", "timeout_minutes", "max_tokens"},
    )
    prefix = f"{where}."
    runtime = _str(table, "runtime", prefix)
    if runtime == OPENCODE and role == "implementer":
        raise ConfigError(
            f"{CONFIG_FILE}: {where}.runtime: opencode is not supported for the {role} role yet"
        )
    if runtime not in RUNTIMES[role]:
        allowed = ", ".join(RUNTIMES[role])
        raise ConfigError(
            f"{CONFIG_FILE}: {where}.runtime: unsupported value {runtime!r} ({allowed})"
        )
    tools = _str_list(table, "tools", prefix)
    if runtime == OPENCODE:
        _opencode_agent(table, tools, where)
    if role == "reviewer" and runtime != OPENCODE:
        writing = [t for t in tools if t in REVIEWER_FORBIDDEN_TOOLS]
        if writing:
            raise ConfigError(
                f"{CONFIG_FILE}: {where}.tools: {writing[0]} is not allowed"
                " (the reviewer is read-only, C10)"
            )
    if "Skill" in tools:
        raise ConfigError(
            f"{CONFIG_FILE}: {where}.tools: Skill is not allowed (undeclared skills, C6)"
        )
    return AgentConfig(
        runtime=runtime,
        model=_str(table, "model", prefix),
        tools=tools,
        max_budget_usd=_positive(table, "max_budget_usd", prefix),
        timeout_minutes=_positive(table, "timeout_minutes", prefix),
        max_tokens=_max_tokens(table, where),
    )


def _opencode_agent(table: dict[str, Any], tools: Sequence[str], where: str) -> None:
    unknown = [t for t in tools if t not in OPENCODE_TOOLS]
    if unknown:
        raise ConfigError(
            f"{CONFIG_FILE}: {where}.tools: {unknown[0]!r} is not an opencode tool"
            f" ({', '.join(OPENCODE_TOOLS)})"
        )
    provider, _, name = _str(table, "model", f"{where}.").partition("/")
    if not provider or not name:
        raise ConfigError(f"{CONFIG_FILE}: {where}.model: opencode wants <provider>/<model>")
    if "max_tokens" not in table:
        raise ConfigError(
            f"{CONFIG_FILE}: {where}.max_tokens: required with opencode"
            " (opencode does not cap its own cost; Ariane needs a token cap)"
        )


def _safe_api_url(url: str) -> bool:
    """https, or plain http to the local machine only (a test server)."""
    parsed = urllib.parse.urlsplit(url)
    if not parsed.hostname:
        return False
    if parsed.scheme == "https":
        return True
    if parsed.scheme != "http":
        return False
    if parsed.hostname == "localhost":
        return True
    try:
        return ipaddress.ip_address(parsed.hostname).is_loopback
    except ValueError:
        return False


def _checks(raw: list[Any]) -> tuple[CheckConfig, ...]:
    checks = []
    names: set[str] = set()
    for index, item in enumerate(raw):
        where = f"checks[{index}]"
        if not isinstance(item, dict):
            raise ConfigError(f"{CONFIG_FILE}: {where}: expected a table")
        _only(item, where, {"name", "command", "blocking", "timeout_minutes"})
        name = _str(item, "name", where + ".")
        if name in names:
            raise ConfigError(f"{CONFIG_FILE}: {where}.name: duplicate check name {name!r}")
        if name.startswith("docs: "):
            raise ConfigError(
                f"{CONFIG_FILE}: {where}.name: {name!r} is reserved (generated checks)"
            )
        names.add(name)
        blocking = item.get("blocking", True)
        if not isinstance(blocking, bool):
            raise ConfigError(f"{CONFIG_FILE}: {where}.blocking: expected true or false")
        checks.append(
            CheckConfig(
                name=name,
                command=_str_list(item, "command", where + "."),
                blocking=blocking,
                timeout_minutes=_positive(item, "timeout_minutes", where + ".", 15),
            )
        )
    return tuple(checks)


def _definition_of_done(data: dict[str, Any], check_names: set[str]) -> tuple[DoneItem, ...]:
    if "definition_of_done" not in data:
        return DEFAULT_DEFINITION_OF_DONE
    table = _table(data, "definition_of_done")
    _only(table, "definition_of_done", {"items"})
    raw = table.get("items")
    if not isinstance(raw, list) or not raw:
        raise ConfigError(f"{CONFIG_FILE}: definition_of_done.items: expected a non-empty list")
    items = []
    for index, item in enumerate(raw):
        where = f"definition_of_done.items[{index}]"
        if not isinstance(item, dict):
            raise ConfigError(f"{CONFIG_FILE}: {where}: expected a table")
        _only(item, where, {"check", "text"})
        if len(item) != 1:
            raise ConfigError(f"{CONFIG_FILE}: {where}: give either check or text")
        if "check" in item:
            name = _str(item, "check", where + ".")
            if name not in check_names:
                raise ConfigError(f"{CONFIG_FILE}: {where}.check: no declared check {name!r}")
            items.append(DoneItem(check=name))
        else:
            items.append(DoneItem(text=_str(item, "text", where + ".")))
    return tuple(items)


def _documentation(data: dict[str, Any]) -> Documentation:
    if "documentation" not in data:
        return NO_DOCUMENTATION
    table = _table(data, "documentation")
    _only(table, "documentation", {"paths", "map", "generated"})
    paths = _str_list(table, "paths", "documentation.") if "paths" in table else ()
    entries = []
    for index, item in enumerate(_table_list(table, "map")):
        where = f"documentation.map[{index}]"
        _only(item, where, {"source", "docs"})
        entries.append(
            DocMapEntry(_str(item, "source", where + "."), _str_list(item, "docs", where + "."))
        )
    generated: list[GeneratedDoc] = []
    for index, item in enumerate(_table_list(table, "generated")):
        where = f"documentation.generated[{index}]"
        _only(item, where, {"name", "check"})
        name = _str(item, "name", where + ".")
        if any(g.name == name for g in generated):
            raise ConfigError(f"{CONFIG_FILE}: {where}.name: duplicate name {name!r}")
        generated.append(GeneratedDoc(name, _str_list(item, "check", where + ".")))
    return Documentation(paths, tuple(entries), tuple(generated))


def _table_list(table: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = table.get(key, [])
    if not isinstance(value, list) or not all(isinstance(v, dict) for v in value):
        raise ConfigError(f"{CONFIG_FILE}: documentation.{key}: expected a list of tables")
    return value


def _only(table: dict[str, Any], where: str, allowed: set[str]) -> None:
    for key in table:
        if key not in allowed:
            dotted = f"{where}.{key}" if where else key
            raise ConfigError(f"{CONFIG_FILE}: {dotted}: unknown key")


def _table(parent: dict[str, Any], key: str, prefix: str = "") -> dict[str, Any]:
    value = parent.get(key)
    if value is None:
        raise ConfigError(f"{CONFIG_FILE}: {prefix}{key}: missing table")
    if not isinstance(value, dict):
        raise ConfigError(f"{CONFIG_FILE}: {prefix}{key}: expected a table")
    return value


def _str(table: dict[str, Any], key: str, prefix: str, default: str | None = None) -> str:
    value = table.get(key, default)
    if value is None:
        raise ConfigError(f"{CONFIG_FILE}: {prefix}{key}: missing key")
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{CONFIG_FILE}: {prefix}{key}: expected a non-empty string")
    return value


def _str_list(table: dict[str, Any], key: str, prefix: str) -> tuple[str, ...]:
    value = table.get(key)
    if value is None:
        raise ConfigError(f"{CONFIG_FILE}: {prefix}{key}: missing key")
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(item, str) and item for item in value)
    ):
        raise ConfigError(
            f"{CONFIG_FILE}: {prefix}{key}: expected a non-empty list of strings"
            " (an argument list, never a shell string)"
        )
    return tuple(value)


def _max_tokens(table: dict[str, Any], where: str) -> int | None:
    value = table.get("max_tokens")
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ConfigError(f"{CONFIG_FILE}: {where}.max_tokens: expected a positive integer")
    return value


def _positive(table: dict[str, Any], key: str, prefix: str, default: float | None = None) -> float:
    value = table.get(key, default)
    if value is None:
        raise ConfigError(f"{CONFIG_FILE}: {prefix}{key}: missing key")
    if (
        isinstance(value, bool)
        or not isinstance(value, int | float)
        or not math.isfinite(value)
        or value <= 0
    ):
        raise ConfigError(f"{CONFIG_FILE}: {prefix}{key}: expected a positive number")
    return float(value)
