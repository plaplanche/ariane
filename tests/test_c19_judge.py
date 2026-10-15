"""C19, C23: `ariane judge` records the human's verdict on a shadow ticket (ADR 0037)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ariane import cli, flow, shadow

from conftest import Project


def make_shadow(project: Project, outcome: str = "delivered") -> Path:
    path = shadow.clone_path(project.root, 7) / "work/7/metrics.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"ticket": 7, "mode": "shadow", "outcome": outcome}), "utf-8")
    return path


def read(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def judge(project: Project, verdict: str, minutes: int, note: str | None = None) -> flow.Outcome:
    return shadow.judge(project.root, 7, verdict, minutes, note)


def test_c19_judge_accept_is_written_with_minutes_and_note(project: Project) -> None:
    path = make_shadow(project)
    outcome = judge(project, "accept", 12, "clean")
    assert outcome.exit_code == 0
    assert "\n" not in outcome.line
    verdict = read(path)["judgement"]
    assert (verdict["verdict"], verdict["minutes"], verdict["note"]) == ("accept", 12, "clean")
    assert verdict["at"].endswith("Z") and "T" in verdict["at"]


def test_c19_judge_reject_without_note_has_a_null_note(project: Project) -> None:
    path = make_shadow(project)
    assert judge(project, "reject", 0).exit_code == 0
    assert read(path)["judgement"]["verdict"] == "reject"
    assert read(path)["judgement"]["note"] is None
    assert "judgements_before" not in read(path)


def test_c19_judge_unknown_ticket(project: Project) -> None:
    outcome = judge(project, "accept", 5)
    assert outcome.exit_code == 1
    assert "no shadow clone" in outcome.line


def test_c19_judge_running_ticket(project: Project) -> None:
    path = make_shadow(project, "running")
    outcome = judge(project, "accept", 5)
    assert outcome.exit_code == 1
    assert "still running" in outcome.line
    assert "judgement" not in read(path)


def test_c19_judge_twice_keeps_the_earlier_judgement(project: Project) -> None:
    path = make_shadow(project)
    judge(project, "accept", 5, "first")
    judge(project, "reject", 9)
    data = read(path)
    assert data["judgement"]["verdict"] == "reject"
    assert [j["note"] for j in data["judgements_before"]] == ["first"]
    judge(project, "accept", 1)
    assert [j["verdict"] for j in read(path)["judgements_before"]] == ["accept", "reject"]


@pytest.mark.parametrize("minutes", [None, "-1", "1441", "x", "1.5"])
def test_c19_judge_minutes_missing_or_out_of_range_are_refused(
    project: Project, monkeypatch: pytest.MonkeyPatch, minutes: str | None
) -> None:
    path = make_shadow(project)
    monkeypatch.chdir(project.root)
    argv = ["judge", "7", "accept"] + ([] if minutes is None else ["--minutes", minutes])
    with pytest.raises(SystemExit) as exc:
        cli.main(argv)
    assert exc.value.code == 2
    assert "judgement" not in read(path)


def test_c19_judge_through_the_command_line(
    project: Project, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path = make_shadow(project)
    monkeypatch.chdir(project.root)
    assert cli.main(["judge", "7", "reject", "--minutes", "1440", "--note", "no"]) == 0
    assert capsys.readouterr().out.count("\n") == 1
    assert read(path)["judgement"]["minutes"] == 1440
