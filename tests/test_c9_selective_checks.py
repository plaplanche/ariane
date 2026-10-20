"""C9: a check declares the files it covers (`checks[].paths`); Ariane skips it when a ticket
changes none of them, and gives every check it runs the list of changed files (ADR 0056)."""

from __future__ import annotations

import copy
import shutil
import sys
from pathlib import Path
from typing import Any

import pytest
from test_config import VALID, with_change
from test_docs_reference import errors

from ariane import checks, config, git, replay, review
from ariane.config import CheckConfig
from ariane.stop import Stop
from ariane.tracker import InMemoryTracker, Issue

from conftest import FakeRuntime, Project, make_config, sh
from test_flow import start, worktree

PY = sys.executable
FAIL = (PY, "-c", "raise SystemExit(1)")
# Copies the file `ARIANE_CHANGED_FILES` names to its output, with the variable's value first.
SHOW = (
    PY,
    "-c",
    "import os, pathlib; p = os.environ['ARIANE_CHANGED_FILES']; print(p);"
    " print(pathlib.Path(p).read_text(encoding='utf-8'), end='')",
)


def check(name: str, paths: tuple[str, ...] = (), command: tuple[str, ...] = FAIL) -> CheckConfig:
    return CheckConfig(name, command, True, 1, paths=paths)


def names(selected: list[CheckConfig]) -> list[str]:
    return [c.name for c in selected]


def replay_plain(
    tmp_path: Path, all_checks: list[CheckConfig], changed: list[str], **kwargs: Any
) -> list[checks.CheckResult]:
    """The replay itself, without git: its trees are plain folders."""
    return replay.replay_each(
        all_checks,
        lambda k: tmp_path / f"tree-{k}",
        create=lambda tree: tree.mkdir(),
        setup=lambda c, tree, env: "",
        verify=lambda tree: None,
        remove=shutil.rmtree,
        env=None,
        trees=[],
        changed=changed,
        records="work/7",
        **kwargs,
    )


def test_c9_selective_checks_unmatched_paths_is_skipped_recorded_and_its_status_says_so(
    project: Project, tracker: InMemoryTracker
) -> None:
    """The fake agent changes `app.txt` only: a check covering `src/**` fails if it runs."""
    cfg = make_config(checks=(check("web", ("src/**",)), check("app", ("*.txt",), (PY, "-V"))))
    runtime = FakeRuntime()
    assert start(project, tracker, runtime, cfg).exit_code == 0
    report = (worktree(project) / "work/7/checks.md").read_text(encoding="utf-8")
    assert "| web | yes | skipped | 0.0 s |" in report
    assert f"## web\n\n- Command: `{' '.join(FAIL)}`\n- Skipped: {checks.SKIPPED}" in report
    assert "| app | yes | pass |" in report
    assert "1 passed, 0 failed (0 blocking), 1 skipped" in report
    status = {s["context"]: s for s in tracker.statuses}
    assert status["ariane/web"]["state"] == "success"
    assert status["ariane/web"]["description"] == f"skipped by Ariane: {checks.SKIPPED}"
    assert status["ariane/app"]["description"].startswith("exit 0, ")
    assert f"Skipped, {checks.SKIPPED}: web." in tracker.opened[0]["body"]
    reviewer = runtime.sessions[-1].prompt
    assert f"Skipped, not run ({checks.SKIPPED}): web." in reviewer
    journal = (worktree(project) / "work/7/journal.md").read_text(encoding="utf-8")
    assert "Checks skipped" in journal


def test_c9_selective_checks_a_matching_file_runs_the_check_also_a_renamed_old_path(
    project: Project,
) -> None:
    assert names(checks.selected([check("web", ("src/**",))], ["src/a.py"], ())) == ["web"]
    sh(["git", "mv", "app.txt", "renamed.md"], project.root)
    sh(["git", "commit", "-q", "-m", "rename"], project.root)
    listing = git.changes(project.root, "HEAD~1", "HEAD", "work").name_status
    assert listing.startswith("R")  # one rename line, not a deletion and an addition
    changed = checks.changed_files(listing)
    assert changed == ["app.txt", "renamed.md"]
    assert names(checks.selected([check("old", ("*.txt",))], changed, ())) == ["old"]
    assert names(checks.selected([check("new", ("*.md",))], changed, ())) == ["new"]


def test_c9_selective_checks_without_paths_always_and_documentation_checks_run(
    tmp_path: Path,
) -> None:
    data = with_change("checks.0.always", True)
    assert config.parse(copy.deepcopy(data)).checks[0].paths == ()
    assert errors(data, config.SCHEMA) == []
    docs = config.Documentation(generated=(config.GeneratedDoc("refs", (PY, "-V")),)).checks()
    plain = check("plain", command=(PY, "-V"))
    scoped = check("scoped", ("src/**",))
    results = replay_plain(tmp_path, [plain, scoped, *docs], ["README.md"])
    assert [(r.name, r.skipped, r.passed) for r in results] == [
        ("plain", False, True),
        ("scoped", True, True),
        ("docs: refs", False, True),
    ]
    assert not checks.blocking_failures(results)


@pytest.mark.parametrize("touched", ["ariane.toml", "uv.lock", ".github/workflows/ci.yml"])
def test_c9_selective_checks_configuration_change_selects_every_check(touched: str) -> None:
    every = [check("web", ("src/**",)), check("app", ("*.txt",))]
    assert names(checks.selected(every, ["docs/a.md", touched], ("uv.lock", ".github/**"))) == [
        "web",
        "app",
    ]
    assert names(checks.selected(every, ["docs/a.md"], ("uv.lock", ".github/**"))) == []
    data = with_change("project.check_all_paths", ["uv.lock", ".github/**"])
    assert config.parse(copy.deepcopy(data)).check_all_paths == ("uv.lock", ".github/**")
    assert errors(data, config.SCHEMA) == []


@pytest.mark.parametrize(
    ("item", "message"),
    [
        ({"paths": ["src/**"], "always": True}, r"checks\[1\]: give either paths or always"),
        ({"paths": []}, r"checks\[1\]\.paths: expected a non-empty list of path globs"),
        ({"paths": ["src/**", 3]}, r"checks\[1\]\.paths: expected a non-empty list of path globs"),
        ({"paths": "src/**"}, r"checks\[1\]\.paths: expected a non-empty list of path globs"),
        ({"always": False}, r"checks\[1\]\.always: expected true"),
    ],
)
def test_c9_selective_checks_schema_refuses_bad_paths_naming_the_check(
    item: dict[str, Any], message: str
) -> None:
    data = copy.deepcopy(VALID)
    data["checks"].append({"name": "web", "command": ["npm", "test"], **item})
    with pytest.raises(config.ConfigError, match=message):
        config.parse(copy.deepcopy(data))
    assert any(e.startswith("checks[1]") for e in errors(data, config.SCHEMA))


def test_c9_selective_checks_check_all_paths_refuses_an_empty_list() -> None:
    with pytest.raises(config.ConfigError, match=r"project\.check_all_paths"):
        config.parse(with_change("project.check_all_paths", []))


def test_c9_selective_checks_changed_files_names_a_file_listing_exactly_them(
    tmp_path: Path,
) -> None:
    changed = ["src/a.py", "old name.txt", "new name.txt"]
    results = replay_plain(tmp_path, [check("show", ("src/**",), SHOW)], changed)
    assert results[0].passed, results[0].output
    path, _, listing = results[0].output.partition("\n")
    assert Path(path) == tmp_path / "tree-1" / "work/7" / checks.CHANGED_FILES
    assert listing.splitlines() == changed


def test_c9_selective_checks_changed_files_refuses_a_listing_the_commit_holds(
    tmp_path: Path,
) -> None:
    def create(tree: Path) -> None:
        (tree / "work/7").mkdir(parents=True)
        (tree / "work/7" / checks.CHANGED_FILES).write_text("forged\n", encoding="utf-8")

    with pytest.raises(Stop, match=r"holds work/7/changed-files\.txt"):
        replay.replay_each(
            [check("show", command=SHOW)],
            lambda k: tmp_path / f"tree-{k}",
            create=create,
            setup=lambda c, tree, env: "",
            verify=lambda tree: None,
            remove=shutil.rmtree,
            env=None,
            trees=[],
            changed=["a"],
            records="work/7",
        )


def test_c9_selective_checks_reviewer_prompt_and_summary_without_skips_are_unchanged() -> None:
    ran = checks.CheckResult("lint", ("ruff",), True, True, "exit 0", "", 1.0)
    prompt = review.prompt(Issue(7, "T", "b", "u"), "", [ran], [check("lint")], ())
    assert "Skipped, not run" not in prompt
    assert checks.summary_line([ran]) == "Summary: 1 passed, 0 failed (0 blocking)."
    skipped = checks.skipped_result(check("web", ("src/**",)))
    assert checks.parse_summary_table(checks.summary_table([skipped])) == [
        ("web", True, "skipped, 0.0 s")
    ]
