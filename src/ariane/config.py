"""Load and validate `ariane.toml` (C22). Every error names the faulty key."""

from __future__ import annotations

import ipaddress
import math
import tomllib
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CONFIG_FILE = "ariane.toml"


_STR: dict[str, Any] = {"type": "string", "minLength": 1}
_ARGV: dict[str, Any] = {"type": "array", "minItems": 1, "items": _STR}
_POSITIVE: dict[str, Any] = {"type": "number", "exclusiveMinimum": 0}

# Description of `ariane.toml` for docs/reference/ariane.toml.schema.json (ADR 0022). Keep it in
# step with `parse`: a test validates both example files against it.
SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "ariane.toml",
    "description": "Configuration of Ariane for one repository.",
    "type": "object",
    "additionalProperties": False,
    "required": ["project", "tracker", "agents", "checks"],
    "properties": {
        "project": {
            "type": "object",
            "additionalProperties": False,
            "required": ["base_branch"],
            "properties": {
                "base_branch": {**_STR, "description": "Branch the pull requests target."},
                "setup": {
                    **_ARGV,
                    "description": "Command run once in the working tree (list of arguments).",
                },
            },
        },
        "tracker": {
            "type": "object",
            "additionalProperties": False,
            "required": ["kind", "repository", "token_env"],
            "properties": {
                "kind": {"enum": ["github"]},
                "repository": {**_STR, "description": "owner/name"},
                "token_env": {**_STR, "description": "Environment variable holding the token."},
                "api_url": {
                    **_STR,
                    "default": "https://api.github.com",
                    "description": "https URL (plain http only to the local machine).",
                },
            },
        },
        "agents": {
            "type": "object",
            "additionalProperties": False,
            "required": ["implementer"],
            "properties": {
                "implementer": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["runtime", "model", "tools", "max_budget_usd", "timeout_minutes"],
                    "properties": {
                        "runtime": {"enum": ["claude-code"]},
                        "model": _STR,
                        "tools": {**_ARGV, "description": "Tools the agent may use (not Skill)."},
                        "max_budget_usd": _POSITIVE,
                        "timeout_minutes": _POSITIVE,
                    },
                }
            },
        },
        "checks": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["name", "command"],
                "properties": {
                    "name": {**_STR, "description": "Unique name of the check."},
                    "command": {**_ARGV, "description": "Command to run (list of arguments)."},
                    "blocking": {"type": "boolean", "default": True},
                    "timeout_minutes": {**_POSITIVE, "default": 15},
                },
            },
        },
    },
}


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


@dataclass(frozen=True)
class CheckConfig:
    name: str
    command: tuple[str, ...]
    blocking: bool
    timeout_minutes: float


@dataclass(frozen=True)
class Config:
    base_branch: str
    setup: tuple[str, ...] | None
    tracker: TrackerConfig
    implementer: AgentConfig
    checks: tuple[CheckConfig, ...]


def load(repo_root: Path) -> Config:
    path = repo_root / CONFIG_FILE
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ConfigError(f"{CONFIG_FILE}: file not found in {repo_root}") from None
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{CONFIG_FILE}: not valid TOML: {exc}") from None
    return parse(data)


def parse(data: dict[str, Any]) -> Config:
    _only(data, "", {"project", "tracker", "agents", "checks"})
    project = _table(data, "project")
    _only(project, "project", {"base_branch", "setup"})
    tracker = _table(data, "tracker")
    _only(tracker, "tracker", {"kind", "repository", "token_env", "api_url"})
    agents = _table(data, "agents")
    _only(agents, "agents", {"implementer"})
    implementer = _table(agents, "implementer", "agents.")
    _only(
        implementer,
        "agents.implementer",
        {"runtime", "model", "tools", "max_budget_usd", "timeout_minutes"},
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
    runtime = _str(implementer, "runtime", "agents.implementer.")
    if runtime != "claude-code":
        raise ConfigError(
            f"{CONFIG_FILE}: agents.implementer.runtime: unsupported value {runtime!r}"
            " (claude-code)"
        )
    tools = _str_list(implementer, "tools", "agents.implementer.")
    if "Skill" in tools:
        raise ConfigError(
            f"{CONFIG_FILE}: agents.implementer.tools: Skill is not allowed (undeclared skills, C6)"
        )

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
    return Config(
        base_branch=base_branch,
        setup=setup,
        tracker=TrackerConfig(
            kind=kind,
            repository=repository,
            token_env=_str(tracker, "token_env", "tracker."),
            api_url=api_url,
        ),
        implementer=AgentConfig(
            runtime=runtime,
            model=_str(implementer, "model", "agents.implementer."),
            tools=tools,
            max_budget_usd=_positive(implementer, "max_budget_usd", "agents.implementer."),
            timeout_minutes=_positive(implementer, "timeout_minutes", "agents.implementer."),
        ),
        checks=_checks(raw_checks),
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
