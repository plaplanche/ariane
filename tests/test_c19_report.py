"""C19, C23: `ariane report` summarises the tickets' metrics files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ariane import cli, git


def put(
    root: Path, rel: str, number: int, started: str, costs: list[float | None], **kw: Any
) -> None:
    data = {
        "ticket": number,
        "mode": kw.get("mode", "delivered"),
        "started": started,
        "sessions": [{"cost_usd": c, "duration_s": 60} for c in costs],
        "rounds": kw.get("rounds", 0),
        "first_pass_verdict": kw.get("verdict", "go"),
        "outcome": "delivered",
    }
    path = root / rel / "metrics.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(data), encoding="utf-8")


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(git, "repo_root", lambda _p: tmp_path)
    return tmp_path


def run(capsys: pytest.CaptureFixture[str], *args: str) -> tuple[int, list[str]]:
    code = cli.main(["report", *args])
    return code, capsys.readouterr().out.splitlines()


def three(repo: Path) -> None:
    put(repo, "work/1", 1, "2026-09-01T10:00:00Z", [0.5, 0.25], rounds=1, verdict="no-go")
    put(repo, "work/2", 2, "2026-10-01T10:00:00Z", [1.0, 1.0])
    put(repo, "work/verify/b", 3, "2026-10-05T10:00:00Z", [0.25], mode="verify")


def test_c19_report_totals_over_three_tickets(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    three(repo)
    code, lines = run(capsys)
    assert code == 0
    assert len(lines) == 5
    assert lines[0].startswith("#1 delivered delivered: cost $0.75, agent time 2m00s, 1 rounds")
    assert "#3 verify" in lines[2]
    assert lines[3] == (
        "Totals: 3 tickets, cost $3.00, agent time 5m00s, 1 rounds, first-pass go rate 2/3 (66%)."
    )


def test_c19_report_since_filters_tickets(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    three(repo)
    code, lines = run(capsys, "--since", "2026-10-01")
    assert code == 0
    assert not any(line.startswith("#1 ") for line in lines)
    assert "Totals: 2 tickets, cost $2.25" in lines[-2]


def test_c19_report_null_cost_is_partly_not_reported(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    put(repo, "work/4", 4, "2026-10-01T10:00:00Z", [None, 0.5])
    _, lines = run(capsys)
    assert "partly not reported" in lines[0]
    assert "partly not reported" in lines[1]


def test_c19_report_without_metrics_says_so(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, lines = run(capsys)
    assert code == 0
    assert len(lines) == 1
    assert "No metrics file" in lines[0]


def test_c19_report_corrupt_file_is_named_and_skipped(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    put(repo, "work/1", 1, "2026-10-01T10:00:00Z", [0.5])
    bad = repo / "work/2/metrics.json"
    bad.parent.mkdir(parents=True)
    bad.write_text("{not json", encoding="utf-8")
    code, lines = run(capsys)
    assert code == 1
    assert "work/2/metrics.json" in lines[0]
    assert "Totals: 1 tickets" in lines[-2]


def test_c19_report_summary_line_is_last(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    three(repo)
    _, lines = run(capsys)
    assert lines[-1] == "Reported 3 tickets. Next: nothing."


def test_c19_report_rejects_a_bad_date(repo: Path) -> None:
    with pytest.raises(SystemExit):
        cli.main(["report", "--since", "yesterday"])
