"""C22: an invalid configuration is refused at start-up with a message naming the faulty key."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest

from ariane import config

VALID: dict[str, Any] = {
    "project": {"base_branch": "main", "setup": ["uv", "sync"]},
    "tracker": {"kind": "github", "repository": "owner/name", "token_env": "GH_TOKEN"},
    "agents": {
        "implementer": {
            "runtime": "claude-code",
            "model": "claude-sonnet-5-5",
            "tools": ["Read", "Edit"],
            "max_budget_usd": 5,
            "timeout_minutes": 30,
        }
    },
    "checks": [{"name": "tests", "command": ["pytest"]}],
}


def with_change(path: str, value: Any) -> dict[str, Any]:
    """VALID with `path` (dotted, list indexes allowed) set to `value`, or removed if None."""
    data = copy.deepcopy(VALID)
    *parents, last = path.split(".")
    node: Any = data
    for part in parents:
        node = node[int(part)] if part.isdigit() else node[part]
    if value is None:
        del node[last]
    else:
        node[last] = value
    return data


def test_c22_a_valid_configuration_is_parsed_with_defaults() -> None:
    cfg = config.parse(copy.deepcopy(VALID))
    assert cfg.setup == ("uv", "sync")
    assert cfg.tracker.api_url == "https://api.github.com"
    assert cfg.implementer.max_budget_usd == 5.0
    check = cfg.checks[0]
    assert (check.command, check.blocking, check.timeout_minutes) == (("pytest",), True, 15.0)


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        ("colour", "blue", "colour: unknown key"),
        ("project.basebranch", "main", "project.basebranch: unknown key"),
        ("project.base_branch", None, "project.base_branch: missing key"),
        ("project.base_branch", 3, "project.base_branch: expected a non-empty string"),
        ("project.setup", "uv sync", "project.setup: expected a non-empty list of strings"),
        ("tracker", None, "tracker: missing table"),
        ("tracker.kind", "jira", "tracker.kind: unsupported value 'jira'"),
        ("tracker.repository", "noslash", "tracker.repository: expected owner/name"),
        ("agents.implementer.runtime", "x", "agents.implementer.runtime: unsupported value"),
        ("agents.implementer.tools", ["Read", "Skill"], "agents.implementer.tools: Skill"),
        ("agents.implementer.max_budget_usd", 0, "agents.implementer.max_budget_usd: expected"),
        ("agents.implementer.timeout_minutes", True, "agents.implementer.timeout_minutes"),
        ("agents.reviewer", {}, "agents.reviewer: unknown key"),
        ("checks", [], "checks: at least one"),
        ("checks.0.command", "pytest -q", "checks[0].command: expected a non-empty list"),
        ("checks.0.blocking", "yes", "checks[0].blocking: expected true or false"),
        ("checks.0.shell", True, "checks[0].shell: unknown key"),
        (
            "agents.implementer.timeout_minutes",
            float("nan"),
            "timeout_minutes: expected a positive",
        ),
        ("agents.implementer.max_budget_usd", float("inf"), "max_budget_usd: expected a positive"),
        ("agents.implementer.max_budget_usd", -1, "max_budget_usd: expected a positive"),
        ("tracker.api_url", "http://api.example.invalid", "tracker.api_url: expected an https"),
        ("tracker.api_url", "ftp://x", "tracker.api_url: expected an https"),
        ("project.base_branch", "-x", "project.base_branch: not a valid branch name"),
        ("project.base_branch", "a b", "project.base_branch: not a valid branch name"),
    ],
)
def test_c22_an_invalid_configuration_names_the_faulty_key(
    path: str, value: Any, message: str
) -> None:
    with pytest.raises(config.ConfigError) as error:
        config.parse(with_change(path, value))
    assert str(error.value).startswith("ariane.toml: ")
    assert message in str(error.value)


@pytest.mark.parametrize(
    "url", ["https://git.example.invalid/api/v3", "http://127.0.0.1:8080", "http://localhost"]
)
def test_c22_https_or_a_local_test_server_is_accepted_as_api_url(url: str) -> None:
    assert config.parse(with_change("tracker.api_url", url)).tracker.api_url == url


def test_c22_duplicate_check_names_are_refused() -> None:
    data = copy.deepcopy(VALID)
    data["checks"].append({"name": "tests", "command": ["pytest"]})
    with pytest.raises(config.ConfigError, match=r"checks\[1\]\.name: duplicate"):
        config.parse(data)


def test_c22_missing_file_and_invalid_toml_are_refused(tmp_path: Path) -> None:
    with pytest.raises(config.ConfigError, match="file not found"):
        config.load(tmp_path)
    (tmp_path / "ariane.toml").write_text("[project\n", encoding="utf-8")
    with pytest.raises(config.ConfigError, match="not valid TOML"):
        config.load(tmp_path)


def test_c22_ariane_own_configuration_is_valid() -> None:
    cfg = config.load(Path(__file__).resolve().parent.parent)
    assert cfg.tracker.repository == "plaplanche/ariane"
    assert "Skill" not in cfg.implementer.tools


def test_c22_example_config_is_accepted() -> None:
    import tomllib

    path = Path(__file__).parent.parent / "docs" / "ariane.example.toml"
    config.parse(tomllib.loads(path.read_text(encoding="utf-8")))


def test_c26_dod_a_valid_table_is_loaded() -> None:
    data = copy.deepcopy(VALID)
    data["definition_of_done"] = {"items": [{"check": "tests"}, {"text": "Docs updated."}]}
    parsed = config.parse(data)
    assert parsed.definition_of_done == (
        config.DoneItem(check="tests"),
        config.DoneItem(text="Docs updated."),
    )


def test_c26_dod_an_undeclared_check_is_refused_naming_the_key() -> None:
    data = copy.deepcopy(VALID)
    data["definition_of_done"] = {"items": [{"check": "nope"}]}
    with pytest.raises(config.ConfigError, match=r"definition_of_done\.items\[0\]\.check"):
        config.parse(data)


def test_c26_dod_an_empty_text_is_refused() -> None:
    data = copy.deepcopy(VALID)
    data["definition_of_done"] = {"items": [{"text": "  "}]}
    with pytest.raises(config.ConfigError, match=r"definition_of_done\.items\[0\]\.text"):
        config.parse(data)


def test_c26_dod_the_default_list_applies_without_a_table() -> None:
    assert config.parse(copy.deepcopy(VALID)).definition_of_done == (
        config.DEFAULT_DEFINITION_OF_DONE
    )
    assert len(config.DEFAULT_DEFINITION_OF_DONE) == 3
