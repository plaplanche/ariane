"""`ariane update <n>` weighs the base's incoming lines in the round's risk tier (C9, C11,
ADR 0033, ADR 0056)."""

from __future__ import annotations

import dataclasses

from test_c11_update import OPEN, move_base, pushes  # noqa: F401 (fixture)

from ariane import update
from ariane.config import CheckConfig, ChecksPolicy
from ariane.tracker import InMemoryTracker

from conftest import PY, FakeRuntime, Project, make_config
from test_flow import environ, start

# A full-suite-only integration check: it fails on the base's large change, if it runs whole.
INTEGRATION = CheckConfig(
    "integration",
    (
        PY,
        "-c",
        "import os, sys; sys.exit(1 if os.environ['ARIANE_FULL_SUITE'] == '1'"
        " and os.path.exists('big.txt') else 0)",
    ),
    True,
    1.0,
    full_when="high",
)


def test_c11_update_a_large_incoming_base_makes_the_round_high(
    project: Project,
    tracker: InMemoryTracker,
    pushes: list[str],  # noqa: F811
) -> None:
    base = make_config()
    config = dataclasses.replace(
        make_config(checks=(*base.checks, INTEGRATION)),
        checks_policy=ChecksPolicy(max_changed_lines=50),
    )
    outcome = start(project, tracker, FakeRuntime(), config)
    assert outcome.exit_code == 0, outcome.line  # the ticket's few lines: low, partial suite
    tracker.pull_states["ariane/7"] = OPEN
    pushes.clear()
    remote = project.remote_branches()["ariane/7"]
    move_base(project, {"big.txt": "".join(f"line {i}\n" for i in range(400))})
    outcome = update.update(
        7,
        repo_root=project.root,
        config=config,
        tracker=tracker,
        runtime=FakeRuntime(),
        environ=environ(),
    )
    assert outcome.exit_code == 1, outcome.line  # 400 incoming lines: high, the full suite
    assert "integration" in outcome.line
    assert pushes == [] and project.remote_branches()["ariane/7"] == remote
