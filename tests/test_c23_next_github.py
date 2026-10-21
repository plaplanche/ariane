"""The GitHub side of `ariane next` against the local HTTP stub: the queue in label order, the
dependencies' state and the relabel (C23, ADR 0060)."""

from __future__ import annotations

import pytest
from test_github import TOKEN, Stub, stub

from ariane.github import GitHubTracker
from ariane.tracker import TrackerError

__all__ = ["stub"]

REPO = "/repos/owner/name"


def tracker(api: str) -> GitHubTracker:
    return GitHubTracker(repository="owner/name", token=TOKEN, api_url=api, ready_label="ariane")


def labelled(name: str, when: str) -> dict[str, object]:
    return {"event": "labeled", "label": {"name": name}, "created_at": when}


def issue(number: int, **extra: object) -> dict[str, object]:
    return {
        "number": number,
        "title": f"Issue {number}",
        "body": f"Body {number}",
        "html_url": f"https://github.com/owner/name/issues/{number}",
        "labels": [{"name": "ariane-next"}, {"name": "docs"}],
        "updated_at": "2026-10-21T09:00:00Z",
        **extra,
    }


def test_c23_next_github_queue_is_in_label_order_without_pull_requests(
    stub: tuple[Stub, str],
) -> None:
    state, api = stub
    listing = [issue(3), issue(4), issue(5, pull_request={}), issue(6)]
    state.responses[("GET", f"{REPO}/issues?state=open&labels=ariane-next&per_page=100&page=1")] = (
        200,
        listing,
    )
    events = {
        3: [labelled("ariane-next", "2026-10-21T10:05:00Z"), labelled("x", "2026-10-21T08:00:00Z")],
        4: [
            labelled("ariane-next", "2026-10-20T10:00:00Z"),
            labelled("ariane-next", "2026-10-21T10:01:00Z"),
        ],
        6: [],  # not listed yet: the issue's last change stands for it
    }
    for number, found in events.items():
        state.responses[("GET", f"{REPO}/issues/{number}/events?per_page=100&page=1")] = (
            200,
            found,
        )
    queue = tracker(api).queue("ariane-next")
    assert [(q.issue.number, q.labelled_at) for q in queue] == [
        (6, "2026-10-21T09:00:00Z"),
        (4, "2026-10-21T10:01:00Z"),
        (3, "2026-10-21T10:05:00Z"),
    ]
    assert queue[0].labels == ("ariane-next", "docs")
    assert queue[0].issue.body == "Body 6"


def test_c23_next_github_closed_as_completed_reads_the_state_reason(
    stub: tuple[Stub, str],
) -> None:
    state, api = stub
    for number, fields in (
        (1, {"state": "closed", "state_reason": "completed"}),
        (2, {"state": "closed", "state_reason": "not_planned"}),
        (3, {"state": "open", "state_reason": None}),
    ):
        state.responses[("GET", f"{REPO}/issues/{number}")] = (200, issue(number, **fields))
    github = tracker(api)
    assert [github.closed_as_completed(n) for n in (1, 2, 3)] == [True, False, False]


def test_c23_next_github_remove_label_ignores_a_missing_label(stub: tuple[Stub, str]) -> None:
    state, api = stub
    github = tracker(api)
    state.responses[("DELETE", f"{REPO}/issues/7/labels/ariane")] = (200, [])
    github.remove_label(7, "ariane")
    github.remove_label(8, "ariane")  # the stub answers 404: the issue lacks the label
    state.responses[("DELETE", f"{REPO}/issues/9/labels/ariane")] = (403, {"message": "no"})
    with pytest.raises(TrackerError, match="HTTP 403"):
        github.remove_label(9, "ariane")
    assert [r["method"] for r in state.requests] == ["DELETE"] * 3


def test_c23_next_github_peek_issue_reads_its_body_and_labels_without_the_gate(
    stub: tuple[Stub, str],
) -> None:
    state, api = stub
    state.responses[("GET", f"{REPO}/issues/12")] = (200, issue(12, labels=[{"name": "docs"}]))
    peeked = tracker(api).peek_issue(12)  # no `ariane` label: the gate would refuse it
    assert (peeked.issue.body, peeked.labels, peeked.labelled_at) == ("Body 12", ("docs",), "")
    state.responses[("GET", f"{REPO}/issues/13")] = (200, {"number": 13})
    with pytest.raises(TrackerError, match="unexpected issue #13"):
        tracker(api).peek_issue(13)
