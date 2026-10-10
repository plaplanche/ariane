"""The generated reference matches the code; the schema agrees with `config.parse` (ADR 0022)."""

from __future__ import annotations

import copy
import importlib.util
import tomllib
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from ariane import cli, config

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "generate_docs.py"
SCHEMA_FILE = ROOT / "docs" / "reference" / "ariane.toml.schema.json"


def load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("generate_docs", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def errors(value: Any, schema: dict[str, Any], where: str = "") -> list[str]:
    """Validate against the subset of JSON Schema that `config.SCHEMA` uses."""
    found: list[str] = []
    here = where or "<root>"
    if "enum" in schema and value not in schema["enum"]:
        found.append(f"{here}: not one of {schema['enum']}")
    kind = schema.get("type")
    if kind == "object":
        if not isinstance(value, dict):
            return [f"{here}: expected an object"]
        props = schema.get("properties", {})
        found += [f"{here}.{k}: missing" for k in schema.get("required", []) if k not in value]
        for key, item in value.items():
            if key in props:
                found += errors(item, props[key], f"{where}.{key}" if where else key)
            elif schema.get("additionalProperties") is False:
                found.append(f"{where}.{key}: unknown key" if where else f"{key}: unknown key")
    elif kind == "array":
        if not isinstance(value, list):
            return [f"{here}: expected an array"]
        if len(value) < schema.get("minItems", 0):
            found.append(f"{here}: too few items")
        for index, item in enumerate(value):
            found += errors(item, schema.get("items", {}), f"{where}[{index}]")
    elif kind == "string":
        if not isinstance(value, str):
            return [f"{here}: expected a string"]
        if len(value) < schema.get("minLength", 0):
            found.append(f"{here}: too short")
    elif kind == "boolean":
        if not isinstance(value, bool):
            found.append(f"{here}: expected a boolean")
    elif kind == "number":
        if isinstance(value, bool) or not isinstance(value, int | float):
            return [f"{here}: expected a number"]
        if "exclusiveMinimum" in schema and value <= schema["exclusiveMinimum"]:
            found.append(f"{here}: must be greater than {schema['exclusiveMinimum']}")
    return found


def load_toml(path: Path) -> dict[str, Any]:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def test_docs_reference_committed_files_match_the_generator() -> None:
    assert load_script().main(["--check"]) == 0


def test_docs_reference_changed_help_text_fails_check(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    script = load_script()
    original = cli._parser

    def changed() -> Any:
        parser = original()
        parser.description = "A different description."
        return parser

    monkeypatch.setattr(cli, "_parser", changed)
    assert script.main(["--check"]) == 1
    assert "docs/reference/cli.md" in capsys.readouterr().out


def test_docs_reference_missing_file_is_named(tmp_path: Path) -> None:
    script = load_script()
    assert script.main(["--check"], root=tmp_path) == 1
    assert script.main([], root=tmp_path) == 0
    assert script.main(["--check"], root=tmp_path) == 0


def test_docs_reference_schema_file_is_the_code_schema() -> None:
    import json

    assert json.loads(SCHEMA_FILE.read_text(encoding="utf-8")) == config.SCHEMA


@pytest.mark.parametrize("name", ["ariane.toml", "docs/ariane.example.toml"])
def test_docs_reference_config_files_validate(name: str) -> None:
    data = load_toml(ROOT / name)
    assert errors(data, config.SCHEMA) == []
    config.parse(data)


def test_docs_reference_unknown_key_rejected_like_parse() -> None:
    data = load_toml(ROOT / "ariane.toml")
    data["tracker"]["colour"] = "red"
    assert errors(data, config.SCHEMA) == ["tracker.colour: unknown key"]
    with pytest.raises(config.ConfigError, match=r"tracker\.colour: unknown key"):
        config.parse(data)


def test_docs_reference_wrong_type_rejected_like_parse() -> None:
    data = load_toml(ROOT / "ariane.toml")
    bad = copy.deepcopy(data)
    bad["agents"]["implementer"]["max_budget_usd"] = "five"
    bad["checks"][0]["command"] = "uv run ruff"
    assert errors(bad, config.SCHEMA) == [
        "agents.implementer.max_budget_usd: expected a number",
        "checks[0].command: expected an array",
    ]
    with pytest.raises(config.ConfigError, match="max_budget_usd"):
        config.parse(bad)
