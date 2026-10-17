"""C11 (ADR 0017): the last guard stops only on URL rewrites that apply to the push URL."""

from __future__ import annotations

from pathlib import Path

import pytest

from ariane import delivery, git
from ariane.tracker import InMemoryTracker

from conftest import FakeRuntime, Project, sh
from test_flow import start

HTTPS = "https://github.com/acme/repo.git"


def _record(pushes: list[str]) -> str:
    pushes.append("push")
    return ""


def _inject(monkeypatch: pytest.MonkeyPatch, pairs: list[tuple[str, str]]) -> None:
    monkeypatch.setenv("GIT_CONFIG_COUNT", str(len(pairs)))
    for n, (key, value) in enumerate(pairs):
        monkeypatch.setenv(f"GIT_CONFIG_KEY_{n}", key)
        monkeypatch.setenv(f"GIT_CONFIG_VALUE_{n}", value)


def _arm(project: Project, monkeypatch: pytest.MonkeyPatch, key: str, prefix: str) -> list[str]:
    """Set a local rewrite key just before the last guard; return the list of pushes."""
    pushes: list[str] = []
    monkeypatch.setattr(git, "push", lambda *a, **k: _record(pushes))
    original = delivery.Delivery._require_replayed

    def late(self: delivery.Delivery) -> None:
        original(self)
        monkeypatch.setattr(git, "snapshot_changes", lambda before, after: [])
        sh(["git", "config", key, prefix], self.worktree)

    monkeypatch.setattr(delivery.Delivery, "_require_replayed", late)
    return pushes


def _remote_url(project: Project) -> str:
    return sh(["git", "config", "remote.origin.url"], project.root).strip()


def test_c11_push_rewrite_environment_ssh_to_https_does_not_apply(
    project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    base = "url.https://github.com/.insteadof"
    _inject(monkeypatch, [(base, "git@github.com:"), (base, "ssh://git@github.com/")])
    assert git.push_rewrites(project.root, HTTPS) == []
    assert git.push_rewrites(project.root, "git@github.com:acme/repo.git") == [
        f"{base}=git@github.com:"
    ]


def test_c11_push_rewrite_environment_keys_do_not_stop_the_delivery(
    project: Project, tracker: InMemoryTracker, monkeypatch: pytest.MonkeyPatch
) -> None:
    base = "url.https://github.com/.insteadof"
    _inject(monkeypatch, [(base, "git@github.com:"), (base, "ssh://git@github.com/")])
    pushes: list[str] = []
    monkeypatch.setattr(git, "push", lambda *a, **k: _record(pushes))
    outcome = start(project, tracker, FakeRuntime())
    assert "rewrites URLs" not in outcome.line
    assert pushes == ["push"]


def test_c11_push_rewrite_matching_pushinsteadof_stops_the_delivery(
    project: Project, tracker: InMemoryTracker, monkeypatch: pytest.MonkeyPatch
) -> None:
    remote = _remote_url(project)
    pushes = _arm(project, monkeypatch, "url.https://elsewhere.invalid/.pushInsteadOf", remote)
    outcome = start(project, tracker, FakeRuntime())
    assert outcome.exit_code == 1
    assert "rewrites URLs" in outcome.line
    assert pushes == []


def test_c11_push_rewrite_matching_insteadof_stops_the_delivery(
    project: Project, tracker: InMemoryTracker, monkeypatch: pytest.MonkeyPatch
) -> None:
    remote = _remote_url(project)
    pushes = _arm(project, monkeypatch, f"url.{remote}.insteadOf", remote)
    outcome = start(project, tracker, FakeRuntime())
    assert outcome.exit_code == 1
    assert "rewrites URLs" in outcome.line
    assert pushes == []


def test_c11_push_rewrite_local_key_with_other_prefix_is_ignored(project: Project) -> None:
    sh(
        ["git", "config", "url.https://elsewhere.invalid/.insteadOf", "git@other.invalid:"],
        project.root,
    )
    assert git.push_rewrites(project.root, HTTPS) == []


def test_c11_push_rewrite_global_key_applies(
    project: Project, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config = tmp_path / "global.config"
    config.write_text('[url "https://evil.invalid/"]\n\tpushInsteadOf = https://github.com/\n')
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))
    assert git.push_rewrites(project.root, HTTPS) == [
        "url.https://evil.invalid/.pushinsteadof=https://github.com/"
    ]


def test_c11_push_rewrite_base_with_equals_sign_is_seen(project: Project) -> None:
    sh(
        ["git", "config", "url.https://evil.invalid/?a=b.pushInsteadOf", "https://github.com/"],
        project.root,
    )
    assert len(git.push_rewrites(project.root, HTTPS)) == 1
