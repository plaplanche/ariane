"""Publish the checks of `work/<n>/checks.md` as commit statuses (C9), from a workflow."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from ariane.checks import parse_summary_table
from ariane.github import GitHubTracker
from ariane.tracker import TrackerError

DESCRIPTION_LIMIT = 140


def main() -> int:
    env = os.environ
    head_ref = env.get("HEAD_REF", "")
    match = re.fullmatch(r"ariane/(\d+)", head_ref)
    if match is None:
        print(f"Branch {head_ref!r} is not ariane/<number>: no status to publish.")
        return 0
    number = match.group(1)
    path = f"work/{number}/checks.md"
    report = Path(path)
    if not report.is_file():
        print(f"No {path}: no status to publish.")
        return 0
    rows = parse_summary_table(report.read_text(encoding="utf-8"))
    tracker = GitHubTracker(
        repository=env["GITHUB_REPOSITORY"],
        token=env["GITHUB_TOKEN"],
        api_url=env.get("GITHUB_API_URL", "https://api.github.com"),
    )
    target_url = tracker.file_url(head_ref, path)
    refused = False
    for name, passed, description in rows:
        state = "success" if passed else "failure"
        try:
            tracker.set_commit_status(
                env["HEAD_SHA"],
                f"ariane/{name}",
                state,
                description[:DESCRIPTION_LIMIT],
                target_url,
            )
        except TrackerError as exc:
            refused = True
            print(f"ariane/{name}: refused: {exc}")
        else:
            print(f"ariane/{name}: {state}")
    return 1 if refused else 0


if __name__ == "__main__":
    sys.exit(main())
