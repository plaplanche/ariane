"""C23 and C22 through the real command line: one line saying what was done and what next."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from ariane import __version__, flow, ticket

from conftest import PY, Project, sh

VALID_TOML = """
[project]
base_branch = "main"

[tracker]
kind = "github"
repository = "owner/name"
token_env = "ARIANE_TEST_TOKEN"

[agents.implementer]
runtime = "claude-code"
model = "m"
tools = ["Read"]
max_budget_usd = 1
timeout_minutes = 1

[agents.reviewer]
runtime = "claude-code"
model = "r"
tools = ["Read"]
max_budget_usd = 1
timeout_minutes = 1

[[checks]]
name = "t"
command = ["pytest"]
"""


def ariane(
    cwd: Path, *args: str, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [PY, "-m", "ariane", *args],
        cwd=cwd,
        env=env if env is not None else dict(os.environ),
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def one_line(done: subprocess.CompletedProcess[str]) -> str:
    lines = done.stdout.splitlines()
    assert len(lines) == 1, done.stdout + done.stderr
    assert " Next: " in lines[0]
    return lines[0]


def test_c23_version(tmp_path: Path) -> None:
    done = ariane(tmp_path, "--version")
    py = sys.version_info
    expected = f"ariane {__version__} (Python {py.major}.{py.minor}.{py.micro}, {sys.platform})"
    assert done.returncode == 0
    assert done.stdout.splitlines() == [expected]


def test_c23_status_without_a_ticket_folder_says_how_to_start(project: Project) -> None:
    done = ariane(project.root, "status", "5")
    assert done.returncode == 1
    assert one_line(done) == "No ticket folder for #5. Next: run ariane start 5."


def test_c23_status_is_read_from_the_ticket_folder(project: Project) -> None:
    folder = ticket.TicketFolder(project.root, 5)
    folder.set_status("delivered", "pull request https://x/1", "review and merge the pull request")
    done = ariane(project.root, "status", "#5")
    assert done.returncode == 0
    line = one_line(done)
    assert line.startswith("Ticket #5 is delivered (pull request https://x/1), read from ")
    assert line.endswith("Next: review and merge the pull request.")


def test_c22_start_refuses_an_invalid_configuration_naming_the_key(project: Project) -> None:
    (project.root / "ariane.toml").write_text(
        VALID_TOML.replace('model = "m"', 'modle = "m"'), encoding="utf-8"
    )
    done = ariane(project.root, "start", "5")
    assert done.returncode == 2
    assert "ariane.toml: agents.implementer.modle: unknown key" in one_line(done)


def test_c23_start_without_a_token_says_which_variable_to_set(project: Project) -> None:
    (project.root / "ariane.toml").write_text(VALID_TOML, encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k != "ARIANE_TEST_TOKEN"}
    done = ariane(project.root, "start", "5", env=env)
    assert done.returncode == 2
    assert "ARIANE_TEST_TOKEN is empty" in one_line(done)


def test_c23_outside_a_git_repository(tmp_path: Path) -> None:
    done = ariane(tmp_path, "status", "1")
    assert done.returncode == 2
    assert "inside a git repository" in one_line(done)


@pytest.mark.parametrize("bad", ["0", "abc", "#x"])
def test_c23_issue_number_is_validated(tmp_path: Path, bad: str) -> None:
    done = ariane(tmp_path, "start", bad)
    assert done.returncode == 2
    assert f"not an issue number: {bad}" in done.stderr


def test_c23_status_reads_the_ticket_working_tree_before_the_main_checkout(
    project: Project,
) -> None:
    ticket.TicketFolder(project.root, 5).set_status("stopped", "old", "x")
    in_worktree = ticket.TicketFolder(flow.worktree_path(project.root, 5), 5)
    in_worktree.set_status("implementing", "implementer session running", "wait")
    line = one_line(ariane(project.root, "status", "5"))
    assert line.startswith("Ticket #5 is implementing (implementer session running)")


def test_c23_no_command_still_ends_with_one_summary_line(tmp_path: Path) -> None:
    done = ariane(tmp_path)
    assert done.returncode == 2
    assert done.stdout.splitlines()[-1] == (
        "Did nothing: no command given. Next: run ariane start <issue>."
    )


def _with_config(project: Project) -> None:
    (project.root / "ariane.toml").write_text(VALID_TOML, encoding="utf-8")


def _deliver(project: Project, number: int) -> None:
    """Push branch `ariane/<n>` holding the ticket folder, as a delivery does."""
    sh(["git", "checkout", "--quiet", "-b", f"ariane/{number}"], project.root)
    folder = ticket.TicketFolder(project.root, number)
    folder.set_status("delivered", "pull request https://x/1", "review and merge")
    sh(["git", "add", "--all"], project.root)
    sh(["git", "commit", "--quiet", "-m", "ticket"], project.root)
    sh(["git", "push", "--quiet", "origin", f"ariane/{number}"], project.root)
    sh(["git", "checkout", "--quiet", "main"], project.root)


def test_c23_status_merged_reads_merged_also_after_the_branch_is_deleted(project: Project) -> None:
    _with_config(project)
    _deliver(project, 5)
    sh(["git", "merge", "--quiet", "--no-ff", "-m", "merge", "ariane/5"], project.root)
    sh(["git", "push", "--quiet", "origin", "main"], project.root)
    sh(["git", "push", "--quiet", "origin", "--delete", "ariane/5"], project.root)
    sh(["git", "branch", "-D", "ariane/5"], project.root)
    shutil.rmtree(project.root / "work")
    line = one_line(ariane(project.root, "status", "5"))
    assert line.startswith("Ticket #5: merged into main (last action: delivered, ")
    assert line.endswith("). Next: nothing.")


def test_c23_status_merged_reads_the_last_action_when_not_merged(project: Project) -> None:
    _deliver(project, 5)
    _with_config(project)
    ticket.TicketFolder(project.root, 5).set_status(
        "delivered", "pull request https://x/1", "review and merge"
    )
    line = one_line(ariane(project.root, "status", "5"))
    assert line.startswith("Ticket #5 is delivered (pull request https://x/1)")
    assert "merged into" not in line


def test_c23_status_merged_without_status_file_answers_in_one_line(project: Project) -> None:
    _with_config(project)
    folder = ticket.folder_path(project.root, 5)
    folder.mkdir(parents=True)
    (folder / "journal.md").write_text("# Journal\n", encoding="utf-8")
    sh(["git", "add", "--all"], project.root)
    sh(["git", "commit", "--quiet", "-m", "records"], project.root)
    sh(["git", "push", "--quiet", "origin", "main"], project.root)
    shutil.rmtree(project.root / "work")
    done = ariane(project.root, "status", "5")
    assert done.returncode == 0
    assert "Traceback" not in done.stderr
    line = one_line(done)
    assert line.startswith("Ticket #5: merged into main (last action unknown")
    assert line.endswith("Next: nothing.")


def test_c23_status_merged_says_when_the_remote_cannot_be_read(project: Project) -> None:
    _with_config(project)
    ticket.TicketFolder(project.root, 5).set_status("delivered", "pull request", "merge it")
    sh(["git", "remote", "set-url", "origin", str(project.root / "missing.git")], project.root)
    line = one_line(ariane(project.root, "status", "5"))
    assert line.startswith("Ticket #5 is delivered (pull request)")
    assert "Could not read the remote" in line
    assert line.endswith("Next: merge it.")


def test_c23_status_merged_reads_an_old_format_status_file(project: Project) -> None:
    _with_config(project)
    folder = ticket.folder_path(project.root, 5)
    folder.mkdir(parents=True)
    (folder / "status.md").write_text(
        "# Status\n\n- State: delivered\n- Updated: 2026-10-08 06:48Z\n- Detail: old\n- Next: go\n",
        encoding="utf-8",
    )
    line = one_line(ariane(project.root, "status", "5"))
    assert line.startswith("Ticket #5 is delivered (old)")
    assert line.endswith("Next: go.")
