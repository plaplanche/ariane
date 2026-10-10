"""C25: a project declares its documentation; untouched documents are flagged; generated ones
are checked in the replay."""

from __future__ import annotations

import copy
import dataclasses

import pytest
from test_config import VALID

from ariane import config, context
from ariane.config import DocMapEntry, Documentation, GeneratedDoc
from ariane.runtime import Session
from ariane.tracker import InMemoryTracker, Issue

from conftest import PY, FakeRuntime, Project, make_config
from test_flow import journal, start, worktree

MAP = Documentation(map=(DocMapEntry("app.*", ("docs/{stem}.md",)),))


def with_docs(docs: Documentation) -> config.Config:
    return dataclasses.replace(make_config(), documentation=docs)


def parse_with(table: object) -> config.Config:
    data = copy.deepcopy(VALID)
    data["documentation"] = table
    return config.parse(data)


def test_c25_docs_the_table_is_loaded() -> None:
    cfg = parse_with(
        {
            "paths": ["docs/", "README.md"],
            "map": [{"source": "src/*.py", "docs": ["docs/{stem}.md"]}],
            "generated": [{"name": "refs", "check": ["x", "--check"]}],
        }
    )
    docs = cfg.documentation
    assert docs.paths == ("docs/", "README.md")
    assert docs.generated == (GeneratedDoc("refs", ("x", "--check")),)
    assert docs.checks()[0].name == "docs: refs" and docs.checks()[0].blocking
    assert config.parse(copy.deepcopy(VALID)).documentation == Documentation()


@pytest.mark.parametrize(
    ("table", "message"),
    [
        ({"generated": [{"name": "refs"}]}, "documentation.generated[0].check: missing key"),
        ({"map": [{"docs": ["a.md"]}]}, "documentation.map[0].source: missing key"),
        ({"map": [{"source": "a"}]}, "documentation.map[0].docs: missing key"),
        ({"generated": [{"name": "r", "check": "x y"}]}, "generated[0].check: expected"),
        ({"colour": 1}, "documentation.colour: unknown key"),
    ],
)
def test_c25_docs_an_invalid_table_is_refused_naming_the_key(
    table: dict[str, object], message: str
) -> None:
    with pytest.raises(config.ConfigError, match=r"\b" + message.replace("[", r"\[")):
        parse_with(table)


def test_c25_docs_stem_expands_and_globs_stay_in_a_folder() -> None:
    entry = DocMapEntry("src/ariane/*.py", ("docs/modules/{stem}.md", "README.md"))
    assert entry.documents_for("src/ariane/flow.py") == ("docs/modules/flow.md", "README.md")
    assert entry.documents_for("src/ariane/sub/flow.py") == ()
    assert entry.documents_for("tests/flow.py") == ()


def test_c25_docs_the_prompt_lists_the_map() -> None:
    issue = Issue(7, "T", "B", "url")
    docs = Documentation(
        map=(DocMapEntry("src/*.py", ("docs/{stem}.md",)),),
        generated=(GeneratedDoc("refs", ("x",)),),
    )
    prompt = context.implementer_prompt(issue, "ariane/7", make_config().checks, documentation=docs)
    assert "Documentation" in prompt and "`src/*.py`: `docs/{stem}.md`" in prompt
    assert "refs" in prompt
    assert "Documentation (" not in context.implementer_prompt(issue, "b", ())


def reviewer_prompt(runtime: FakeRuntime) -> str:
    return next(s.prompt for s in runtime.sessions if s.role == "reviewer")


def test_c25_docs_an_untouched_document_is_journaled_and_given_to_the_reviewer(
    project: Project, tracker: InMemoryTracker
) -> None:
    runtime = FakeRuntime()
    outcome = start(project, tracker, runtime, with_docs(MAP))
    assert outcome.exit_code == 0  # flagged, not stopped
    text = journal(project)
    assert "Documentation not updated" in text and "`docs/app.md`" in text
    assert "`docs/app.md`" in reviewer_prompt(runtime)


def test_c25_docs_a_changed_document_is_not_flagged(
    project: Project, tracker: InMemoryTracker
) -> None:
    def edit_both(session: Session) -> None:
        (session.cwd / "app.txt").write_text("version 2\n", encoding="utf-8")
        (session.cwd / "docs").mkdir()
        (session.cwd / "docs" / "app.md").write_text("doc\n", encoding="utf-8")

    runtime = FakeRuntime(action=edit_both)
    assert start(project, tracker, runtime, with_docs(MAP)).exit_code == 0
    assert "Documentation not updated" not in journal(project)
    assert "did not touch" not in reviewer_prompt(runtime)


def test_c25_docs_a_stale_generated_document_fails_the_replay(
    project: Project, tracker: InMemoryTracker
) -> None:
    stale = Documentation(generated=(GeneratedDoc("refs", (PY, "-c", "raise SystemExit(1)")),))
    outcome = start(project, tracker, FakeRuntime(), with_docs(stale))
    assert outcome.exit_code == 1
    assert "blocking checks failed: docs: refs" in outcome.line
    report = (worktree(project) / "work/7/checks.md").read_text(encoding="utf-8")
    assert "## docs: refs" in report


def test_c25_docs_without_the_table_nothing_changes(
    project: Project, tracker: InMemoryTracker
) -> None:
    runtime = FakeRuntime()
    assert start(project, tracker, runtime).exit_code == 0
    assert "Documentation not updated" not in journal(project)
    assert "Documentation (" not in runtime.sessions[0].prompt
