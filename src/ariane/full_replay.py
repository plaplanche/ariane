"""The sampled full replay after delivery (C9, C19, ADR 0056): every check with
`ARIANE_FULL_SUITE=1`, in fresh replay trees of the delivered commit, to catch and count what
selective checks missed. It never changes the push, the pull request or the review."""

from __future__ import annotations

import hashlib
import time
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from ariane import checks, git, replay, ticket
from ariane.config import Config
from ariane.delivery import FAILURES, Delivered
from ariane.redact import redact
from ariane.risk import DEFAULT_FULL_REPLAY_SAMPLE, FULL_SUITE_VARIABLE
from ariane.stop import Stop, describe
from ariane.tracker import TrackerError

if TYPE_CHECKING:
    from ariane.flow import _TicketRun

RECORD = "full-replay.md"
STATUS = "ariane/full-replay"
_STATUS_DESCRIPTION_MAX = 140
SKIPPED = "skipped"
PARTIAL = "partial"
RAN = "ran in full"


def sample_of(config: Config) -> float:
    """`[checks_policy] full_replay_sample`, its default without the table."""
    policy = config.checks_policy
    return DEFAULT_FULL_REPLAY_SAMPLE if policy is None else policy.full_replay_sample


def sampled(number: int, commit: str, fraction: float) -> bool:
    """Whether ticket `number` at `commit` gets a full replay: a draw from both alone, so a rerun
    gives the same choice; never with 0, always with 1."""
    if fraction <= 0:
        return False
    digest = hashlib.sha256(f"ariane full replay {number} {commit}".encode()).digest()
    return int.from_bytes(digest[:8], "big") < fraction * 2**64


def selective(round_: dict[str, Any] | None) -> bool:
    """A round's measures (`Metrics.replayed`) show a check skipped or run partly."""
    return round_ is not None and bool(round_["skipped"] or round_["partial"])


def escapes(
    round_results: Sequence[checks.CheckResult], full: Sequence[checks.CheckResult]
) -> list[checks.CheckResult]:
    """The checks that fail in the full replay although they passed (or were skipped) in the
    selective round: a check that failed there already is no escape."""
    passed = {r.name for r in round_results if r.passed}
    return [r for r in full if not r.passed and r.name in passed]


def how(name: str, round_: dict[str, Any]) -> str:
    """How the selective round treated check `name`: skipped, partial, or ran in full."""
    if name in round_["skipped"]:
        return SKIPPED
    return PARTIAL if name in round_["partial"] else RAN


def after_delivery(
    run: _TicketRun, checked: str, results: Sequence[checks.CheckResult], done: Delivered
) -> None:
    """After the delivery of `checked`: when its round passed its blocking checks with one
    skipped or partial, draw the sample, then fully replay, record, journal and publish. Every
    record goes in a local commit; a stop here is recorded and ends the full replay only."""
    round_ = run.metrics.replays[-1] if run.metrics.replays else None
    if round_ is None or not selective(round_) or checks.blocking_failures(results):
        return
    fraction = sample_of(run.config)
    if not sampled(run.number, checked, fraction):
        run.metrics.full_replayed(False)
        run.folder.log(
            "ticket.checks.full_replay",
            "Full replay not sampled",
            f"`full_replay_sample` = {fraction:g}: ticket #{run.number} at `{checked}` is not"
            " in the sample.",
        )
        run._commit_record(f"#{run.number}: record the full replay")
        return
    run.folder.log(
        "ticket.checks.full_replay",
        "Full replay started",
        f"`full_replay_sample` = {fraction:g}: every check, `{FULL_SUITE_VARIABLE}=1`, each in"
        f" its own clean working tree at `{checked}`, after pull request #{done.pull_number}."
        f"\n\n{_round_line(round_)}",
    )
    began = time.monotonic()
    try:
        guard = run.state().snapshot  # after the delivery: the pushed branch is the baseline
        refs = git.remote_refs(run.worktree, run.url)
        full = replay.replay(run, checked, run.start_commit, guard, refs, full=True)
    except (Stop, KeyboardInterrupt, *FAILURES) as exc:
        reason, _ = describe(exc)
        detail = exc.detail if isinstance(exc, Stop) else str(exc)
        run.metrics.full_replayed(True, time.monotonic() - began, stopped=reason)
        run.folder.write(RECORD, f"# Full replay\n\nStopped: {reason}.\n\n{detail}\n")
        run.folder.log("ticket.checks.full_replay", f"Full replay stopped: {reason}", detail)
        run._commit_record(f"#{run.number}: record the full replay")
        return
    escaped = escapes(results, full)
    run.metrics.full_replayed(True, time.monotonic() - began, [r.name for r in escaped])
    run.folder.write(RECORD, record(full, escaped, round_, checked, fraction))
    if escaped:
        run.folder.log(
            "ticket.checks.escape",
            f"Escape: {', '.join(r.name for r in escaped)}",
            "\n".join(f"- {r.name} ({how(r.name, round_)}): {r.detail}" for r in escaped),
        )
    else:
        run.folder.log(
            "ticket.checks.full_replay", "Full replay passed", checks.summary_table(full)
        )
    _publish(run, done, escaped, round_, checked)
    run._commit_record(f"#{run.number}: record the full replay")


def _round_line(round_: dict[str, Any]) -> str:
    skipped = ", ".join(round_["skipped"]) or "none"
    partial = ", ".join(round_["partial"]) or "none"
    return f"Selective round: skipped {skipped}; partial (`{FULL_SUITE_VARIABLE}=0`) {partial}."


def record(
    full: Sequence[checks.CheckResult],
    escaped: Sequence[checks.CheckResult],
    round_: dict[str, Any],
    checked: str,
    fraction: float,
) -> str:
    """`full-replay.md`: each check's selective and full results, then each escape's output."""
    names = {r.name for r in escaped}
    lines = [
        "# Full replay\n",
        f"Replayed by Ariane after the delivery, on commit `{checked}`: every check,"
        f" `{FULL_SUITE_VARIABLE}=1`, each in its own clean working tree"
        f" (`full_replay_sample` = {fraction:g}).\n",
        _round_line(round_) + "\n",
        "| Check | Selective round | Full replay | Escape |",
        "| --- | --- | --- | --- |",
    ]
    for r in full:
        verdict = "pass" if r.passed else f"**fail** ({r.detail})"
        escape = "yes" if r.name in names else "no"
        lines.append(f"| {r.name} | {how(r.name, round_)} | {verdict} | {escape} |")
    lines += ["", f"Escapes: {len(escaped)}.", ""]
    for r in escaped:
        lines += [
            f"## {r.name} (escape)\n",
            f"- Command: `{' '.join(r.command)}`",
            f"- Selective round: {how(r.name, round_)}",
            f"- Full replay: failed ({r.detail}, {r.duration_s:.1f} s)",
            "",
            ticket.fenced(r.output) + "\n",
        ]
    return "\n".join(lines) + "\n"


def _publish(
    run: _TicketRun,
    done: Delivered,
    escaped: Sequence[checks.CheckResult],
    round_: dict[str, Any],
    checked: str,
) -> None:
    """The `ariane/full-replay` status on the pushed commit, and on an escape a comment on the
    pull request naming the failing checks; a refusal is a journaled warning."""
    names = ", ".join(r.name for r in escaped)
    shown = f"escape: {names} failed only in the full replay" if escaped else "full replay passed"
    description = redact(shown, run.secrets)[:_STATUS_DESCRIPTION_MAX]
    state = "failure" if escaped else "success"
    try:
        run.tracker.set_commit_status(done.pushed, STATUS, state, description, done.pull_url)
    except TrackerError as exc:
        run.folder.log(
            "ticket.warning.statuses_refused",
            "Warning: commit statuses refused",
            f"- `{STATUS}`: {exc}",
        )
    if not escaped:
        return
    listing = "\n".join(f"- `{r.name}` ({how(r.name, round_)}): {r.detail}" for r in escaped)
    body = (
        f"**Escape**: Ariane's full replay after delivery (every check, `{FULL_SUITE_VARIABLE}=1`,"
        f" commit `{checked}`) failed checks that passed in the selective round:\n\n"
        f"{listing}\n\nThe outputs are in `{ticket.relative_folder(run.number)}/{RECORD}`."
    )
    try:
        run.tracker.comment(done.pull_number, redact(body, run.secrets))
    except TrackerError as exc:
        run.folder.log("ticket.warning.comment_refused", "Warning: comment refused", str(exc))
