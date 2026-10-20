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

from ariane.cache import CacheConfig, CacheConfigError
from ariane.cache import parse as parse_caches
from ariane.config_schema import (
    CODEX,
    OPENCODE,
    PI,
    RUNTIMES,
    SCHEMA,
    agent_problem,
    model_problem,
)
from ariane.risk import FULL_WHEN, ChecksPolicy, PolicyError
from ariane.risk import parse as parse_policy

__all__ = ["CODEX", "OPENCODE", "PI", "SCHEMA", "CacheConfig", "ChecksPolicy"]

CONFIG_FILE = "ariane.toml"
CONFIG_ENV = "ARIANE_CONFIG"
DEFAULT_IDLE_MINUTES = 10.0
FULL_REPLAY_CHECK = "full-replay"  # checks publish `ariane/<name>`: the full replay's (ADR 0056)


class ConfigError(Exception):
    """The configuration is missing or invalid."""


@dataclass(frozen=True)
class TrackerConfig:
    kind: str
    repository: str
    token_env: str
    api_url: str
    ready_label: str = "ariane"


@dataclass(frozen=True)
class AgentConfig:
    runtime: str
    model: str
    tools: tuple[str, ...]
    max_budget_usd: float
    timeout_minutes: float
    max_tokens: int | None = None
    api_key_env: str | None = None  # codex, pi: variable holding an API key, else CLI's login
    idle_minutes: float | None = None  # no event for this long stops the session; None: no limit
    small: SmallReview | None = None  # reviewer only: settings for a small change (ADR 0046)


@dataclass(frozen=True)
class SmallReview:
    """`[agents.reviewer.small]`: what replaces the reviewer's values for a change of at most
    `max_lines` changed lines; None keeps the reviewer's (ADR 0046)."""

    max_lines: int
    model: str | None = None
    max_budget_usd: float | None = None
    max_tokens: int | None = None
    timeout_minutes: float | None = None


@dataclass(frozen=True)
class CheckConfig:
    name: str
    command: tuple[str, ...]
    blocking: bool
    timeout_minutes: float
    setup: tuple[str, ...] | None = None  # replaces project.setup in this check's replay tree
    not_run_locally: tuple[str, ...] = ()  # globs of the files whose tests only CI runs
    paths: tuple[str, ...] = ()  # globs of the files it covers; () selects it always
    full_when: str = "high"  # "high" or "always": when it gets ARIANE_FULL_SUITE=1 (ADR 0056)


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


def matching_paths(globs: Sequence[str], paths: Sequence[str]) -> list[str]:
    """The `paths` that match at least one of the `globs`."""
    regexes = [_glob_regex(g) for g in globs]
    return [p for p in paths if any(r.fullmatch(p) for r in regexes)]


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
    return re.compile("".join(out), re.DOTALL)  # a line break in a file name is matched too


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
    env: tuple[str, ...] = ()  # variables the project's checks need (ADR 0024)
    parallel_checks: int = 1  # checks replayed at the same time (ADR 0052)
    caches: tuple[CacheConfig, ...] = ()  # `[[project.cache]]`: dependency folders (ADR 0054)
    check_all_paths: tuple[str, ...] = ()  # globs whose change selects every check
    checks_policy: ChecksPolicy | None = None  # `[checks_policy]`; None: every round is high
    sensitive_paths: tuple[str, ...] = ()  # `[review]`: globs labelled for the owner (ADR 0057)


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
    tables = {"project", "tracker", "agents", "checks", "definition_of_done", "documentation"}
    _only(data, "", {*tables, "checks_policy", "review"})
    review = _table(data, "review") if "review" in data else {}
    _only(review, "review", {"sensitive_paths"})
    project = _table(data, "project")
    keys = {"base_branch", "setup", "env", "parallel_checks", "cache", "check_all_paths"}
    _only(project, "project", keys)
    tracker = _table(data, "tracker")
    _only(tracker, "tracker", {"kind", "repository", "token_env", "api_url", "ready_label"})
    agents = _table(data, "agents")
    _only(agents, "agents", {"implementer", "reviewer"})
    implementer = _agent(agents, "implementer")
    reviewer = _agent(agents, "reviewer")
    if reviewer.model == implementer.model:
        raise ConfigError(
            f"{CONFIG_FILE}: agents.reviewer.model: must differ from agents.implementer.model"
            f" ({reviewer.model!r}); the review is by a different model (C10)"
        )
    if reviewer.small is not None and reviewer.small.model == implementer.model:
        raise ConfigError(
            f"{CONFIG_FILE}: agents.reviewer.small.model: must differ from"
            f" agents.implementer.model ({implementer.model!r}); the review is by a different"
            " model (C10)"
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

    ready_label = _str(tracker, "ready_label", "tracker.", "ariane")
    if not ready_label.strip():
        raise ConfigError(f"{CONFIG_FILE}: tracker.ready_label: must not be empty")

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
            ready_label=ready_label,
        ),
        implementer=implementer,
        reviewer=reviewer,
        checks=checks,
        definition_of_done=_definition_of_done(data, names),
        documentation=documentation,
        env=_env(project),
        parallel_checks=_count(project, "parallel_checks", "project") or 1,
        caches=_caches(project),
        check_all_paths=_globs(project, "project", "check_all_paths"),
        checks_policy=_checks_policy(data),
        sensitive_paths=_globs(review, "review", "sensitive_paths"),
    )


def _caches(project: dict[str, Any]) -> tuple[CacheConfig, ...]:
    try:
        return parse_caches(project.get("cache", []))
    except CacheConfigError as exc:
        raise ConfigError(f"{CONFIG_FILE}: {exc}") from None


def _checks_policy(data: dict[str, Any]) -> ChecksPolicy | None:
    try:
        return parse_policy(data.get("checks_policy"))
    except PolicyError as exc:
        raise ConfigError(f"{CONFIG_FILE}: {exc}") from None


def _env(project: dict[str, Any]) -> tuple[str, ...]:
    value = project.get("env", [])
    if not isinstance(value, list) or not all(isinstance(v, str) and v.strip() for v in value):
        raise ConfigError(
            f"{CONFIG_FILE}: project.env: expected a list of variable names"
            " (an entry ending in _ is a prefix)"
        )
    return tuple(value)


def _agent(agents: dict[str, Any], role: str) -> AgentConfig:
    where = f"agents.{role}"
    table = _table(agents, role, "agents.")
    _only(
        table,
        where,
        {
            "runtime",
            "model",
            "tools",
            "max_budget_usd",
            "timeout_minutes",
            "idle_minutes",
            "max_tokens",
            "api_key_env",
            *(("small",) if role == "reviewer" else ()),
        },
    )
    prefix = f"{where}."
    runtime = _str(table, "runtime", prefix)
    if runtime in (OPENCODE, CODEX, PI) and role == "implementer":
        raise ConfigError(
            f"{CONFIG_FILE}: {where}.runtime: {runtime} is not supported for the {role} role yet"
        )
    if runtime not in RUNTIMES[role]:
        allowed = ", ".join(RUNTIMES[role])
        raise ConfigError(
            f"{CONFIG_FILE}: {where}.runtime: unsupported value {runtime!r} ({allowed})"
        )
    tools = _str_list(table, "tools", prefix)
    api_key_env = _str(table, "api_key_env", prefix) if "api_key_env" in table else None
    model = _str(table, "model", prefix)
    problem = agent_problem(role, runtime, model, tools, api_key_env, "max_tokens" in table)
    if problem is not None:
        raise ConfigError(f"{CONFIG_FILE}: {where}.{problem[0]}: {problem[1]}")
    timeout_minutes = _positive(table, "timeout_minutes", prefix)
    return AgentConfig(
        runtime=runtime,
        model=model,
        tools=tools,
        max_budget_usd=_positive(table, "max_budget_usd", prefix),
        timeout_minutes=timeout_minutes,
        max_tokens=_count(table, "max_tokens", where),
        api_key_env=api_key_env,
        idle_minutes=_idle_minutes(table, where, timeout_minutes),
        small=_small(table, where, runtime, api_key_env) if "small" in table else None,
    )


def _small(table: dict[str, Any], where: str, runtime: str, api_key_env: str | None) -> SmallReview:
    """`[agents.reviewer.small]`: same runtime and tools as the reviewer (ADR 0046)."""
    small = _table(table, "small", f"{where}.")
    prefix = f"{where}.small."
    _only(
        small,
        prefix[:-1],
        {"max_lines", "model", "max_budget_usd", "max_tokens", "timeout_minutes"},
    )
    lines = _count(small, "max_lines", prefix[:-1])
    if lines is None:
        raise ConfigError(f"{CONFIG_FILE}: {prefix}max_lines: missing key")
    model = _str(small, "model", prefix) if "model" in small else None
    problem = model and model_problem(runtime, model, api_key_env)
    if problem:
        raise ConfigError(f"{CONFIG_FILE}: {prefix}model: {problem}")
    numbers = {
        k: _positive(small, k, prefix) for k in ("max_budget_usd", "timeout_minutes") if k in small
    }
    return SmallReview(lines, model, max_tokens=_count(small, "max_tokens", prefix[:-1]), **numbers)


def _idle_minutes(table: dict[str, Any], where: str, timeout_minutes: float) -> float | None:
    """The idle limit (ADR 0045): below the time limit; by default 10 minutes, or none when the
    time limit is 10 minutes or less."""
    if "idle_minutes" not in table:
        return DEFAULT_IDLE_MINUTES if timeout_minutes > DEFAULT_IDLE_MINUTES else None
    idle = _positive(table, "idle_minutes", f"{where}.")
    if idle >= timeout_minutes:
        raise ConfigError(
            f"{CONFIG_FILE}: {where}.idle_minutes: must be below {where}.timeout_minutes"
            f" ({timeout_minutes:g})"
        )
    return idle


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
        keys = {"name", "command", "blocking", "timeout_minutes", "setup", "not_run_locally"}
        _only(item, where, {*keys, "paths", "always", "full_when"})
        if item.get("full_when", "high") not in FULL_WHEN:
            raise ConfigError(f'{CONFIG_FILE}: {where}.full_when: expected "high" or "always"')
        if "paths" in item and "always" in item:
            raise ConfigError(f"{CONFIG_FILE}: {where}: give either paths or always, not both")
        if item.get("always", True) is not True:
            raise ConfigError(
                f"{CONFIG_FILE}: {where}.always: expected true (without paths, a check always runs)"
            )
        name = _str(item, "name", where + ".")
        if name in names:
            raise ConfigError(f"{CONFIG_FILE}: {where}.name: duplicate check name {name!r}")
        if name.startswith("docs: ") or name == FULL_REPLAY_CHECK:
            what = "generated checks" if name != FULL_REPLAY_CHECK else "the full replay's status"
            raise ConfigError(f"{CONFIG_FILE}: {where}.name: {name!r} is reserved ({what})")
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
                setup=_str_list(item, "setup", where + ".") if "setup" in item else None,
                not_run_locally=_globs(item, where, "not_run_locally"),
                paths=_globs(item, where, "paths"),
                full_when=item.get("full_when", "high"),
            )
        )
    return tuple(checks)


def _globs(item: dict[str, Any], where: str, key: str) -> tuple[str, ...]:
    if key not in item:
        return ()
    value = item[key]
    if not isinstance(value, list) or not value or not all(isinstance(v, str) and v for v in value):
        raise ConfigError(f"{CONFIG_FILE}: {where}.{key}: expected a non-empty list of path globs")
    return tuple(value)


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


def _count(table: dict[str, Any], key: str, where: str) -> int | None:
    """A positive integer, or None when `key` is absent."""
    value = table.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ConfigError(f"{CONFIG_FILE}: {where}.{key}: expected a positive integer")
    return value


def _positive(table: dict[str, Any], key: str, prefix: str, default: float | None = None) -> float:
    value = table.get(key, default)
    if value is None:
        raise ConfigError(f"{CONFIG_FILE}: {prefix}{key}: missing key")
    numeric = isinstance(value, int | float) and not isinstance(value, bool)
    if not numeric or not math.isfinite(value) or value <= 0:
        raise ConfigError(f"{CONFIG_FILE}: {prefix}{key}: expected a positive number")
    return float(value)
