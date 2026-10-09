"""Replay the declared checks and publish them as commit statuses (C9), from a workflow.

The statuses come from running the checks here, never from a report file in the branch.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from ariane import checks, config, process
from ariane.github import GitHubTracker
from ariane.tracker import TrackerError

DESCRIPTION_LIMIT = 140
SETUP_TIMEOUT_S = 1800.0


def setup_failure(cfg: config.Config, cwd: Path) -> str | None:
    """Run the declared setup command; return why it failed, or None."""
    if not cfg.setup:
        return None
    try:
        done = process.run(cfg.setup, cwd=cwd, timeout_s=SETUP_TIMEOUT_S)
    except process.CommandNotFoundError as exc:
        return str(exc)
    if done.ok:
        return None
    return "timed out" if done.timed_out else f"exit {done.returncode}"


def main() -> int:
    env = os.environ
    head_ref = env.get("HEAD_REF", "")
    if not head_ref.startswith("ariane/"):
        print(f"Branch {head_ref!r} is not ariane/*: no status to publish.")
        return 0
    root = Path.cwd()
    try:
        cfg = config.load(root)
    except config.ConfigError as exc:
        print(f"Cannot publish statuses: {exc}")
        return 1
    failed_setup = setup_failure(cfg, root)
    if failed_setup is None:
        results = checks.run_checks(cfg.checks, root)
    else:
        print(f"Setup failed: {failed_setup}")
        results = [
            checks.CheckResult(c.name, c.command, c.blocking, False, "setup failed", "", 0.0)
            for c in cfg.checks
        ]
    tracker = GitHubTracker(
        repository=env["GITHUB_REPOSITORY"],
        token=env["GITHUB_TOKEN"],
        api_url=env.get("GITHUB_API_URL", "https://api.github.com"),
    )
    server = env.get("GITHUB_SERVER_URL", "https://github.com").rstrip("/")
    target_url = f"{server}/{env['GITHUB_REPOSITORY']}/actions/runs/{env.get('GITHUB_RUN_ID', '')}"
    refused = False
    for result in results:
        state = "success" if result.passed else "failure"
        description = f"{'pass' if result.passed else result.detail}, {result.duration_s:.1f} s"
        try:
            tracker.set_commit_status(
                env["HEAD_SHA"],
                f"ariane/{result.name}",
                state,
                description[:DESCRIPTION_LIMIT],
                target_url,
            )
        except TrackerError as exc:
            refused = True
            print(f"ariane/{result.name}: refused: {exc}")
        else:
            print(f"ariane/{result.name}: {state}")
    return 1 if refused else 0


if __name__ == "__main__":
    sys.exit(main())
