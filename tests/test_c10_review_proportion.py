"""C10, C26: the reviewer knows the residuals the owner accepted and the ticket's scope; a change
to a sensitive path is labelled for the owner (ADR 0057)."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
import test_github
from test_config import with_change
from test_github import Stub, stub  # noqa: F401 (fixture)

from ariane import config, git, review, verify
from ariane.config import Config
from ariane.delivery import OWNER_REVIEW_LABEL
from ariane.runtime import Session
from ariane.tracker import InMemoryTracker

from conftest import FakeRuntime, Project, commit_on_branch, edit_app, make_config, sh
from test_flow import environ, journal, start

BASE_ADR = """# 0001. Guard

## Consequences

- **Accepted residual.** Until a sandbox, an agent running as the same user can
  forge a registry entry.
- Not a residual.
"""
ADDED_ADR = "# 0002. New\n\n- **Accepted residual.** Added by the change itself.\n"


def commit_base_adr(project: Project) -> None:
    folder = project.root / "docs" / "adr"
    folder.mkdir(parents=True)
    (folder / "0001-guard.md").write_text(BASE_ADR, encoding="utf-8")
    sh(["git", "add", "--all"], project.root)
    sh(["git", "commit", "--quiet", "-m", "ADR 0001"], project.root)
    sh(["git", "push", "--quiet", "origin", "main"], project.root)


def add_residual(session: Session) -> None:
    edit_app(session)
    folder = session.cwd / "docs" / "adr"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "0002-new.md").write_text(ADDED_ADR, encoding="utf-8")


def reviewer_prompt(runtime: FakeRuntime) -> str:
    return next(s.prompt for s in runtime.sessions if s.role == "reviewer")


def sensitive(*globs: str) -> Config:
    return dataclasses.replace(make_config(), sensitive_paths=globs)


def test_c10_review_proportion_the_prompt_lists_the_base_residuals_and_the_proportion_rule(
    project: Project, tracker: InMemoryTracker
) -> None:
    commit_base_adr(project)
    runtime = FakeRuntime(action=add_residual)
    assert start(project, tracker, runtime).exit_code == 0
    prompt = reviewer_prompt(runtime)
    block = prompt.partition('<untrusted-ticket kind="accepted-residuals">\n')[2]
    listed = block.partition("</untrusted-ticket>")[0]
    assert listed == (
        "- ADR 0001: Until a sandbox, an agent running as the same user can forge a registry"
        " entry.\n"
    )
    assert '"accepted residual (ADR NNNN)" in its title' in prompt
    assert "- Proportion: a case that neither the ticket nor the specification asks for" in prompt
    assert "loses data, breaks a security property or\n  makes a check pass wrongly" in prompt


def test_c10_review_proportion_a_residual_added_by_the_change_is_not_listed(
    project: Project, tracker: InMemoryTracker
) -> None:
    commit_base_adr(project)
    runtime = FakeRuntime(action=add_residual)
    assert start(project, tracker, runtime).exit_code == 0
    prompt = reviewer_prompt(runtime)
    listed = prompt.partition('kind="accepted-residuals">')[2].partition("</untrusted-ticket>")[0]
    assert "Added by the change itself." not in listed
    assert "+- **Accepted residual.** Added by the change itself." in prompt  # in the diff only


def test_c10_review_proportion_without_residuals_no_block_but_the_proportion_rule(
    project: Project, tracker: InMemoryTracker
) -> None:
    runtime = FakeRuntime()
    assert start(project, tracker, runtime).exit_code == 0
    prompt = reviewer_prompt(runtime)
    assert "accepted-residuals" not in prompt
    assert "accepted residual (ADR NNNN)" not in prompt
    assert "- Proportion:" in prompt


def test_c10_review_proportion_a_sensitive_change_is_labelled_for_the_owner(
    project: Project, tracker: InMemoryTracker
) -> None:
    runtime = FakeRuntime()
    assert start(project, tracker, runtime, sensitive("src/**", "*.txt")).exit_code == 0
    [opened] = tracker.opened
    assert tracker.labels == {1001: [OWNER_REVIEW_LABEL]}
    body = str(opened["body"])
    line = "**Owner review** (`owner-review`): sensitive paths changed: `app.txt`.\n\n## Review"
    assert line in body
    prompt = reviewer_prompt(runtime)
    assert "This change touches sensitive paths (`[review] sensitive_paths`)" in prompt
    assert '<untrusted-ticket kind="paths">\napp.txt\n</untrusted-ticket>' in prompt


def test_c10_review_proportion_a_change_outside_the_sensitive_paths_is_not_labelled(
    project: Project, tracker: InMemoryTracker
) -> None:
    runtime = FakeRuntime()
    assert start(project, tracker, runtime, sensitive("src/**", ".github/**")).exit_code == 0
    assert tracker.labels == {}
    assert "Owner review" not in str(tracker.opened[-1]["body"])
    assert "sensitive paths" not in reviewer_prompt(runtime)


def test_c10_review_proportion_a_refused_label_is_a_warning(
    project: Project, tracker: InMemoryTracker
) -> None:
    tracker.refuse_labels = True
    assert start(project, tracker, FakeRuntime(), sensitive("app.txt")).exit_code == 0
    assert "Warning: label owner-review refused" in journal(project)
    assert "sensitive paths changed: `app.txt`" in str(tracker.opened[-1]["body"])


def test_c10_review_proportion_residuals_are_read_at_the_given_commit(tmp_path: Path) -> None:
    sh(["git", "init", "--quiet", "--initial-branch=main", str(tmp_path)], tmp_path)
    (tmp_path / "docs" / "adr").mkdir(parents=True)
    (tmp_path / "README.md").write_text("- **Accepted residual.** Not an ADR.\n", encoding="utf-8")
    sh(["git", "add", "--all"], tmp_path)
    sh(["git", "commit", "--quiet", "-m", "no ADR"], tmp_path)
    assert review.accepted_residuals(tmp_path, "HEAD") == []
    (tmp_path / "docs/adr/0001-guard.md").write_text(BASE_ADR, encoding="utf-8")
    sh(["git", "add", "--all"], tmp_path)
    sh(["git", "commit", "--quiet", "-m", "ADR"], tmp_path)
    base = sh(["git", "rev-parse", "HEAD"], tmp_path)
    (tmp_path / "docs/adr/0002-new.md").write_text(ADDED_ADR, encoding="utf-8")
    sh(["git", "add", "--all"], tmp_path)
    sh(["git", "commit", "--quiet", "-m", "later"], tmp_path)
    found = review.accepted_residuals(tmp_path, base)
    assert found == [
        review.Residual(
            "0001", "Until a sandbox, an agent running as the same user can forge a registry entry."
        )
    ]
    assert len(review.accepted_residuals(tmp_path, "HEAD")) == 2


def test_c10_review_proportion_the_repository_adrs_carry_the_marker() -> None:
    root = Path(__file__).resolve().parent.parent / "docs" / "adr"
    for name in ("0017", "0031", "0047"):
        [path] = root.glob(f"{name}-*.md")
        assert review.residual_items(path.read_text(encoding="utf-8")), name


def test_c10_review_proportion_sensitive_paths_in_the_configuration() -> None:
    globs = [".github/**", "src/ariane/git.py"]
    parsed = config.parse(with_change("review", {"sensitive_paths": globs}))
    assert parsed.sensitive_paths == tuple(globs)
    assert config.parse(with_change("project.env", [])).sensitive_paths == ()
    with pytest.raises(config.ConfigError, match=r"review\.other: unknown key"):
        config.parse(with_change("review", {"other": 1}))
    with pytest.raises(config.ConfigError, match=r"review\.sensitive_paths: expected"):
        config.parse(with_change("review", {"sensitive_paths": []}))


def test_c10_review_proportion_github_adds_the_label_to_the_pull_request(
    stub: tuple[Stub, str],  # noqa: F811 (fixture)
) -> None:
    state, url = stub
    state.responses[("POST", "/repos/owner/name/issues/12/labels")] = (200, [])
    test_github.tracker(url).add_labels(12, [OWNER_REVIEW_LABEL])
    [request] = state.requests
    assert (request["method"], request["path"]) == ("POST", "/repos/owner/name/issues/12/labels")
    assert request["body"] == {"labels": ["owner-review"]}


def test_c10_review_proportion_verify_gives_the_merge_base_residuals_and_sensitive_paths(
    project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    commit_base_adr(project)
    files = {"app.txt": "version 2\n", "docs/adr/0002-new.md": ADDED_ADR}
    commit_on_branch(project.root, "hand/fix", "By hand", files, parent="main")
    monkeypatch.setattr(git, "push", lambda *a, **k: None)
    runtime = FakeRuntime()
    outcome = verify.verify(
        "hand/fix",
        repo_root=project.root,
        config=sensitive("app.txt"),
        runtime=runtime,
        environ=environ(),
    )
    assert outcome.exit_code == 0, outcome.line
    prompt = reviewer_prompt(runtime)
    listed = prompt.partition('kind="accepted-residuals">\n')[2].partition("</untrusted-ticket>")[0]
    assert listed.startswith("- ADR 0001: Until a sandbox,") and "Added by" not in listed
    assert '<untrusted-ticket kind="paths">\napp.txt\n</untrusted-ticket>' in prompt


GUARD = "".join(f"guard line {i}\n" for i in range(20))


def commit_guard(project: Project) -> None:
    (project.root / "guard.py").write_text(GUARD, encoding="utf-8")
    sh(["git", "add", "--all"], project.root)
    sh(["git", "commit", "--quiet", "-m", "guard"], project.root)
    sh(["git", "push", "--quiet", "origin", "main"], project.root)


def move_guard(session: Session) -> None:
    edit_app(session)
    (session.cwd / "tools").mkdir(exist_ok=True)
    sh(["git", "mv", "guard.py", "tools/moved.py"], session.cwd)
    sh(["git", "commit", "--quiet", "-m", "Move the guard"], session.cwd)  # git sees a rename


def test_c10_review_proportion_renaming_a_sensitive_file_away_is_labelled(
    project: Project, tracker: InMemoryTracker
) -> None:
    commit_guard(project)
    runtime = FakeRuntime(action=move_guard)
    assert start(project, tracker, runtime, sensitive("guard.py")).exit_code == 0
    assert "R100\tguard.py\ttools/moved.py" in reviewer_prompt(runtime)  # a rename, not a delete
    assert tracker.labels == {1001: [OWNER_REVIEW_LABEL]}
    assert "sensitive paths changed: `guard.py`." in str(tracker.opened[-1]["body"])
    assert '<untrusted-ticket kind="paths">\nguard.py\n</untrusted-ticket>' in reviewer_prompt(
        runtime
    )


def test_c10_review_proportion_verify_sees_a_sensitive_file_renamed_away(
    project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    commit_guard(project)
    sh(["git", "switch", "--quiet", "-c", "hand/move"], project.root)
    (project.root / "app.txt").write_text("version 2\n", encoding="utf-8")
    (project.root / "tools").mkdir()
    sh(["git", "mv", "guard.py", "tools/moved.py"], project.root)
    sh(["git", "commit", "--quiet", "-am", "Move the guard"], project.root)
    sh(["git", "switch", "--quiet", "main"], project.root)
    monkeypatch.setattr(git, "push", lambda *a, **k: None)
    runtime = FakeRuntime()
    outcome = verify.verify(
        "hand/move",
        repo_root=project.root,
        config=sensitive("guard.py"),
        runtime=runtime,
        environ=environ(),
    )
    assert outcome.exit_code == 0, outcome.line
    prompt = reviewer_prompt(runtime)
    assert "R100\tguard.py\ttools/moved.py" in prompt
    assert '<untrusted-ticket kind="paths">\nguard.py\n</untrusted-ticket>' in prompt
