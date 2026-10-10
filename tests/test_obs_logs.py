"""Technical logs by level and the catalogue of log types (ADR 0022, spec "Observability")."""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

import pytest
from test_cli import VALID_TOML

from ariane import cli, logs, ticket

from conftest import Project

ROOT = Path(__file__).resolve().parent.parent
TOKEN = "ghp_" + "a1B2c3D4e5" * 4


def run_status(project: Project, monkeypatch: pytest.MonkeyPatch, *args: str) -> int:
    monkeypatch.chdir(project.root)
    return cli.main(["status", "1", *args])


def test_obs_logs_debug_appears_at_debug_not_at_warning(
    project: Project, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv(logs.LEVEL_VARIABLE, raising=False)
    run_status(project, monkeypatch)
    assert "git.command" not in capsys.readouterr().err
    run_status(project, monkeypatch, "--log-level", "debug")
    err = capsys.readouterr().err
    assert "DEBUG git.command" in err
    assert "process.exited" in err


def test_obs_logs_option_wins_over_variable(
    project: Project, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv(logs.LEVEL_VARIABLE, "debug")
    run_status(project, monkeypatch)
    assert "git.command" in capsys.readouterr().err
    run_status(project, monkeypatch, "--log-level", "error")
    assert "git.command" not in capsys.readouterr().err


def test_obs_logs_invalid_level_is_refused(
    project: Project, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run_status(project, monkeypatch, "--log-level", "loud") == cli.EXIT_USAGE
    out = capsys.readouterr().out
    assert len(out.splitlines()) == 1
    assert "invalid log level 'loud'" in out
    monkeypatch.setenv(logs.LEVEL_VARIABLE, "loud")
    assert run_status(project, monkeypatch) == cli.EXIT_USAGE


def test_obs_logs_token_is_masked_in_stderr_and_file(
    project: Project, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path = logs.log_path(project.root, 7)
    logs.configure(logs.LEVELS["debug"], path)
    logs.add_secrets(["plain-secret-value"])
    logs.emit("github.request", f"GET /x with {TOKEN} and plain-secret-value")
    logs.configure(logs.LEVELS["warning"])
    err = capsys.readouterr().err
    text = path.read_text(encoding="utf-8")
    for seen in (err, text):
        assert "github.request" in seen
        assert TOKEN not in seen
        assert "plain-secret-value" not in seen
        assert "***" in seen


def test_obs_logs_file_is_outside_the_repository_and_appended(
    project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    (project.root / "ariane.toml").write_text(VALID_TOML, encoding="utf-8")
    run_status(project, monkeypatch, "--log-level", "debug")
    run_status(project, monkeypatch, "--log-level", "debug")
    path = logs.log_path(project.root, 1)
    assert path == project.root.parent / "proj.ariane" / "logs" / "1.log"
    assert project.root not in path.parents
    assert path.read_text(encoding="utf-8").count("git.command") >= 2
    logs.configure(logs.LEVELS["warning"])


def test_obs_logs_journal_entry_needs_a_declared_type(tmp_path: Path) -> None:
    folder = ticket.TicketFolder(tmp_path, 1)
    with pytest.raises(ValueError, match="undeclared"):
        folder.log("made.up", "Title")


def test_obs_logs_every_log_call_uses_a_declared_type() -> None:
    seen = 0
    for source in (ROOT / "src" / "ariane").glob("*.py"):
        for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
                continue
            first = node.args[0] if node.args else None
            if node.func.attr == "log" and len(node.args) >= 2 and source.name != "logs.py":
                assert isinstance(first, ast.Constant), (source.name, node.lineno)
                assert first.value in logs.FUNCTIONAL_TYPES, (source.name, node.lineno)
                seen += 1
            if node.func.attr == "emit" and isinstance(first, ast.Constant):
                assert first.value in logs.TECHNICAL_TYPES, (source.name, node.lineno)
                seen += 1
    assert seen >= 15


def test_obs_logs_warning_in_journal_is_a_technical_warning(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    logs.configure(logs.LEVELS["warning"])
    folder = ticket.TicketFolder(tmp_path, 1)
    folder.log("ticket.warning.statuses_refused", "Warning: commit statuses refused", "- x")
    logs.configure(logs.LEVELS["warning"])
    assert "WARNING journal.warning" in capsys.readouterr().err


def test_obs_logs_catalogue_matches_the_declarations() -> None:
    spec = importlib.util.spec_from_file_location(
        "generate_docs", ROOT / "scripts" / "generate_docs.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    text = (ROOT / "docs" / "logs.md").read_text(encoding="utf-8")
    assert text == module.render_logs()
    for declared in (*logs.FUNCTIONAL_TYPES.values(), *logs.TECHNICAL_TYPES.values()):
        assert f"| `{declared.id}` | {declared.level} | {declared.meaning} |" in text
