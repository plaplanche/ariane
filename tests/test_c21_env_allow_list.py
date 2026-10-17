"""C21: agents, checks and setup commands receive an allow list of variables (ADR 0024)."""

from __future__ import annotations

import dataclasses
import sys
from pathlib import Path
from typing import Any

import pytest
from test_config import with_change
from test_docs_reference import errors

from ariane import config, context
from ariane.tracker import InMemoryTracker

from conftest import FakeRuntime, Project, make_config
from test_flow import journal, start

CLAUDE = ("ANTHROPIC_", "CLAUDE_")
UNDECLARED = {
    "DATABASE_URL": "postgres://u:p@db/x",
    "GITHUB_PAT": "ghp_x",
    "KUBECONFIG": "/home/x/.kube/config",
    "MY_SETTING": "my-value",
    "GIT_AUTHOR_NAME": "Someone",
}
BASE_SET = {
    "PATH": "/bin",
    "HOME": "/home/x",
    "USER": "x",
    "LOGNAME": "x",
    "SHELL": "/bin/sh",
    "LANG": "C.UTF-8",
    "LANGUAGE": "en",
    "LC_ALL": "C",
    "TZ": "UTC",
    "TERM": "xterm",
    "TMPDIR": "/tmp",
    "TMP": "/tmp",
    "TEMP": "/tmp",
    "HTTPS_PROXY": "http://proxy:3128",
    "http_proxy": "http://proxy:3128",
    "No_Proxy": "localhost",
    "ALL_PROXY": "socks5://proxy",
    "SSL_CERT_FILE": "/etc/ca.pem",
    "SSL_CERT_DIR": "/etc/ssl",
    "REQUESTS_CA_BUNDLE": "/etc/ca.pem",
    "NODE_EXTRA_CA_CERTS": "/etc/ca.pem",
    "CURL_CA_BUNDLE": "/etc/ca.pem",
}


def envs(base: dict[str, str], declared: tuple[str, ...] = ()) -> list[dict[str, str]]:
    """The checks' environment, then an agent session's."""
    return [
        context.untrusted_environment(
            base, token_env="GH_TOKEN", remotes=[], declared=declared, is_root=False
        ),
        context.untrusted_environment(
            base,
            token_env="GH_TOKEN",
            remotes=[],
            login_variables=CLAUDE,
            declared=declared,
            is_root=False,
        ),
    ]


def test_c21_env_allow_list_an_undeclared_variable_is_absent() -> None:
    for env in envs({**BASE_SET, **UNDECLARED, "ANTHROPIC_API_KEY": "a"}):
        assert set(UNDECLARED).isdisjoint(env)
        assert not set(UNDECLARED.values()) & set(env.values())


def test_c21_env_allow_list_the_base_set_proxies_and_certificates_pass() -> None:
    for env in envs(BASE_SET):
        assert {k: env[k] for k in BASE_SET} == BASE_SET
        assert env["GIT_SSH_COMMAND"] == "ariane-ssh-is-disabled-for-agents"


def test_c21_env_allow_list_windows_variables_pass_on_windows_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    windows = {"SYSTEMROOT": "C:\\Windows", "ProgramFiles(x86)": "C:\\P", "PATHEXT": ".EXE"}
    monkeypatch.setattr(sys, "platform", "linux")
    for env in envs(windows):
        assert set(windows).isdisjoint(env)
    monkeypatch.setattr(sys, "platform", "win32")
    for env in envs(windows):
        assert {k: env[k] for k in windows} == windows


def test_c21_env_allow_list_declared_names_and_prefixes_pass_but_never_the_token() -> None:
    base = {
        "MY_SETTING": "1",
        "MYAPP_HOST": "h",
        "myapp_port": "2",
        "MYAPPX": "no",
        "GH_TOKEN": "tok",
        "ARIANE_CONFIG": "x.toml",
        "VIRTUAL_ENV": "/v",
    }
    declared = ("my_setting", "MYAPP_", "GH_TOKEN", "ARIANE_", "ARIANE_CONFIG", "VIRTUAL_ENV")
    for env in envs(base, declared):
        assert env["MY_SETTING"] == "1" and env["MYAPP_HOST"] == "h" and env["myapp_port"] == "2"
        assert "MYAPPX" not in env
        assert "GH_TOKEN" not in env and "ARIANE_CONFIG" not in env and "VIRTUAL_ENV" not in env
    assert context.declared_secrets(base, declared, "GH_TOKEN") == ""


def test_c21_env_allow_list_a_declared_secret_passes_and_is_named() -> None:
    base = {"DATABASE_URL": "postgres://u:p@db/x", "NPM_TOKEN": "npm-s3cret", "MY_SETTING": "1"}
    declared = ("DATABASE_URL", "NPM_", "MY_SETTING")
    for env in envs(base, declared):
        assert env["DATABASE_URL"] == base["DATABASE_URL"] and env["NPM_TOKEN"] == "npm-s3cret"
    note = context.declared_secrets(base, declared, "GH_TOKEN")
    assert "`DATABASE_URL`, `NPM_TOKEN`" in note and "MY_SETTING" not in note
    assert "s3cret" not in note and "postgres" not in note


def test_c21_env_allow_list_a_declared_secret_is_journaled_once_by_name(
    project: Project, tracker: InMemoryTracker, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SERVICE_PASSWORD", "pw-s3cret")
    cfg = dataclasses.replace(make_config(), env=("SERVICE_PASSWORD",))
    start(project, tracker, FakeRuntime(), cfg)
    text = journal(project)
    assert text.count("Declared secrets passed") == 1
    assert "`SERVICE_PASSWORD`" in text and "pw-s3cret" not in text


def test_c21_env_allow_list_no_journal_entry_without_a_declared_secret(
    project: Project, tracker: InMemoryTracker
) -> None:
    start(project, tracker, FakeRuntime())
    assert "Declared secrets passed" not in journal(project)


def test_c21_env_allow_list_known_secrets_hold_the_extended_patterns() -> None:
    secret = {
        "DATABASE_URL": "a",
        "GITHUB_PAT": "b",
        "PAT_FOR_CI": "c",
        "STRIPE_KEY": "d",
        "SENTRY_DSN": "e",
        "REGISTRY_AUTH": "f",
        "KUBECONFIG": "g",
        "DOCKER_AUTH_CONFIG": "h",
        "NPM_TOKEN": "i",
    }
    plain = {"PATH": "p", "PATHEXT": "q", "GIT_AUTHOR_NAME": "r", "KEYBOARD": "s", "MY": "t"}
    assert sorted(context.known_secrets({**secret, **plain}, "GH_TOKEN")) == sorted(secret.values())


def test_c21_env_allow_list_project_env_is_validated() -> None:
    assert config.parse(with_change("project.env", [])).env == ()
    assert config.parse(with_change("project.env", ["A", "B_"])).env == ("A", "B_")
    assert config.parse(with_change("project.setup", ["uv", "sync"])).env == ()
    for bad in ("A", [1], [""], ["A", None]):
        with pytest.raises(config.ConfigError, match=r"project\.env: expected a list"):
            config.parse(with_change("project.env", bad))


def test_c21_env_allow_list_project_env_is_in_the_schema() -> None:
    data: dict[str, Any] = with_change("project.env", ["A", "B_"])
    assert errors(data, config.SCHEMA) == []
    assert errors(with_change("project.env", ["A", 1]), config.SCHEMA) != []
    assert errors(with_change("project.env", "A"), config.SCHEMA) != []


def test_c21_env_allow_list_ariane_declares_an_empty_list() -> None:
    root = Path(__file__).resolve().parent.parent
    assert config.load(root).env == ()
    assert "env = []" in (root / "docs" / "ariane.example.toml").read_text(encoding="utf-8")


def test_c21_env_allow_list_a_proxy_url_with_credentials_passes_only_if_declared() -> None:
    """ADR 0024: proxies pass by default, but a proxy URL with credentials is the project's to
    declare; once declared it passes and is named in the journal."""
    base = {
        "HTTPS_PROXY": "http://user:s3cret@proxy:3128",
        "http_proxy": "user:s3cret@proxy:3128",
        "ALL_PROXY": "socks5://proxy:1080",
        "NO_PROXY": "user@example.invalid",
    }
    for env in envs(base):
        assert "HTTPS_PROXY" not in env and "http_proxy" not in env
        assert env["ALL_PROXY"] == base["ALL_PROXY"] and env["NO_PROXY"] == base["NO_PROXY"]
        assert "s3cret" not in "".join(env.values())
    declared = ("HTTPS_PROXY", "http_proxy")
    for env in envs(base, declared):
        assert env["HTTPS_PROXY"] == base["HTTPS_PROXY"] and env["http_proxy"] == base["http_proxy"]
    note = context.declared_secrets(base, declared, "GH_TOKEN")
    assert "`HTTPS_PROXY`, `http_proxy`" in note and "s3cret" not in note
