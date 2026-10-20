"""C9: a check declares the files it covers (`checks[].paths`); Ariane skips it when a ticket
changes none of them, and gives every check it runs the list of changed files (ADR 0056)."""

from __future__ import annotations

import copy
import os
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


def test_c9_selective_checks_quoted_paths_are_decoded_also_a_rename_source(
    project: Project,
) -> None:
    """Git quotes a path holding a double quote, a backslash or a control character, even with
    core.quotepath=off: the selection and the listing use the real path."""
    if sys.platform == "win32":
        pytest.skip("a double quote is not allowed in a Windows file name")
    (project.root / "src").mkdir()
    (project.root / 'src/a"b.py').write_text("x\n", encoding="utf-8")
    (project.root / "old\\été.txt").write_text("y\n", encoding="utf-8")
    sh(["git", "add", "."], project.root)
    sh(["git", "commit", "-q", "-m", "add"], project.root)
    sh(["git", "mv", "old\\été.txt", "new.md"], project.root)
    sh(["git", "commit", "-q", "-m", "rename"], project.root)
    added = git.changes(project.root, "HEAD~2", "HEAD~1", "work").name_status
    assert '"src/a\\"b.py"' in added  # git's own spelling is quoted
    assert sorted(checks.changed_files(added)) == ["old\\été.txt", 'src/a"b.py']
    renamed = checks.changed_files(git.changes(project.root, "HEAD~1", "HEAD", "work").name_status)
    assert renamed == ["old\\été.txt", "new.md"]
    assert names(checks.selected([check("old", ("old*.txt",))], renamed, ())) == ["old"]
    assert names(checks.selected([check("web", ("src/**",))], ['src/a"b.py'], ())) == ["web"]
    assert checks.git_path('"tab\\there\\303\\251"') == "tab\thereé"
    assert checks.git_path("plain.txt") == "plain.txt"


def test_c9_selective_checks_cleanup_spares_a_listing_outside_after_its_folder_moved(
    tmp_path: Path,
) -> None:
    """A check moves `work/7` away and puts a link to an outside folder holding a file of the
    listing's name in its place: the outside file survives the cleanup."""
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / checks.CHANGED_FILES).write_text("keep\n", encoding="utf-8")
    swap = (
        PY,
        "-c",
        "import os; os.rename('work/7', 'work/moved');"
        f" os.symlink({str(outside)!r}, 'work/7', target_is_directory=True)",
    )
    seen: list[bool] = []

    def verify(tree: Path) -> None:
        seen.append((outside / checks.CHANGED_FILES).exists())

    try:
        results = replay.replay_each(
            [check("swap", command=swap)],
            lambda k: tmp_path / f"tree-{k}",
            create=lambda tree: tree.mkdir(),
            setup=lambda c, tree, env: "",
            verify=verify,
            remove=shutil.rmtree,
            env=None,
            trees=[],
            changed=["a"],
            records="work/7",
        )
    except OSError:  # no right to make a link (Windows without developer mode)
        pytest.skip("links cannot be made here")
    if not results[0].passed and "symlink" in results[0].output:
        pytest.skip("links cannot be made here")
    assert results[0].passed, results[0].output
    assert seen == [True]
    assert (outside / checks.CHANGED_FILES).read_text(encoding="utf-8") == "keep\n"


by_handle = pytest.mark.skipif(
    not checks._BY_HANDLE, reason="folders are opened by handle on POSIX only (ADR 0056)"
)


def _swap_to_link(folder: Path, outside: Path) -> None:
    """What a parallel check may do: move `folder` away and put a link to `outside` there."""
    folder.rename(folder.with_name(folder.name + "-moved"))
    folder.symlink_to(outside, target_is_directory=True)


@by_handle
@pytest.mark.parametrize("swapped", ["work", "work/7"])
def test_c9_selective_checks_listing_never_lands_outside_when_a_folder_swaps_while_made(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, swapped: str
) -> None:
    """A parallel check replaces a folder of the listing's path by a link to an outside folder
    right after Ariane made it: the listing is never written outside the tree."""
    outside = tmp_path / "outside"
    outside.mkdir()
    tree = tmp_path / "tree"
    tree.mkdir()
    real_mkdir = os.mkdir

    def mkdir(path: Any, *args: Any, **kwargs: Any) -> None:
        real_mkdir(path, *args, **kwargs)
        if Path(path).name == Path(swapped).name and not (tree / swapped).is_symlink():
            _swap_to_link(tree / swapped, outside)

    monkeypatch.setattr(os, "mkdir", mkdir)
    with (
        pytest.raises(Stop, match="leads outside the replay tree"),
        checks.changed_files_listing(tree, "work/7", ["a"]),
    ):
        pass
    assert list(outside.iterdir()) == []


@by_handle
def test_c9_selective_checks_nothing_is_removed_by_name_after_the_check(tmp_path: Path) -> None:
    """A parallel check swaps the listing itself for another file, or its folder for a link to
    an outside folder: Ariane removes nothing by name after the check, so neither the swapped-in
    file nor the outside one is touched; the replay tree's removal takes what is left."""
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / checks.CHANGED_FILES).write_text("keep\n", encoding="utf-8")
    tree = tmp_path / "tree"
    tree.mkdir()
    with checks.changed_files_listing(tree, "work/7", ["a"]) as listing:
        assert listing.read_text(encoding="utf-8") == "a\n"
        os.replace(listing, tree / "moved.txt")
        listing.write_text("swapped in\n", encoding="utf-8")
    assert listing.read_text(encoding="utf-8") == "swapped in\n"
    with checks.changed_files_listing(tree, "work/8", ["a"]):
        if hasattr(os, "symlink") and os.name != "nt":
            _swap_to_link(tree / "work/8", outside)
    assert (outside / checks.CHANGED_FILES).read_text(encoding="utf-8") == "keep\n"


def test_c9_selective_checks_the_verification_leaves_only_the_listing_out() -> None:
    status = "\n".join(
        [
            "?? work/7/changed-files.txt",
            "?? work/7/changed-files.txt/inside",
            "?? work/7/changed-files.txt.bak",
            " M app.txt",
        ]
    )
    assert checks.without_listing(status, "work/7") == "?? work/7/changed-files.txt.bak\n M app.txt"
    assert checks.without_listing("", "work/7") == ""


def test_c9_selective_checks_a_unicode_line_separator_keeps_the_name_whole(
    project: Project,
) -> None:
    """Git ends a record at a line feed only: a name holding U+2028 stays one path, from the
    raw diff to the listing, and `unlistable` refuses it rather than skip its check."""
    name = "src/name\u2028tail.py"
    (project.root / "src").mkdir()
    (project.root / name).write_text("x\n", encoding="utf-8")
    sh(["git", "-c", "core.quotepath=off", "add", "--", name], project.root)
    sh(["git", "commit", "-q", "-m", "separator"], project.root)
    changes = git.changes(project.root, "HEAD~1", "HEAD", "work")
    changed = checks.changed_files(changes.name_status)
    assert changed == [name]
    assert checks.unlistable(checks.changed_files("M\t" + name)) == [name]


@by_handle
def test_c9_selective_checks_listing_refuses_a_linked_folder_of_the_commit(
    tmp_path: Path,
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / "tree/work").mkdir(parents=True)
    (tmp_path / "tree/work/7").symlink_to(outside, target_is_directory=True)
    with (
        pytest.raises(Stop, match="leads outside the replay tree"),
        checks.changed_files_listing(tmp_path / "tree", "work/7", ["a"]),
    ):
        pass
    assert list(outside.iterdir()) == []


def test_c9_selective_checks_listing_by_path_writes_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Windows goes by path: the same listing, left for the replay tree's removal."""
    monkeypatch.setattr(checks, "_BY_HANDLE", False)
    with checks.changed_files_listing(tmp_path, "work/7", ["a", "b c"]) as listing:
        assert listing.read_bytes() == b"a\nb c\n"
    assert listing.exists()
    (tmp_path / "work/7" / checks.CHANGED_FILES).write_text("forged\n", encoding="utf-8")
    with (
        pytest.raises(Stop, match="holds work/7/changed-files"),
        checks.changed_files_listing(tmp_path, "work/7", ["a"]),
    ):
        pass


def test_c9_selective_checks_a_line_break_in_a_name_is_matched_and_stops_the_listing(
    tmp_path: Path,
) -> None:
    """`**` matches a file name holding a line break, and the replay stops before any check
    rather than give a list where that name reads as two paths."""
    broken = "src/line\nbreak.py"
    assert names(checks.selected([check("web", ("src/**",))], [broken], ())) == ["web"]
    assert names(checks.selected([check("web", ("src/*.py",))], [broken], ())) == ["web"]
    assert checks.git_path('"src/line\\nbreak.py"') == broken
    with pytest.raises(Stop, match="holds a line break") as stopped:
        replay_plain(tmp_path, [check("show", ("src/**",), SHOW)], ["a.py", broken])
    assert repr(broken) in stopped.value.detail
    assert not (tmp_path / "tree-1").exists()
