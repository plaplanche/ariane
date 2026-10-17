"""The cap and timeout texts the runtimes and the reviewer share (C5, C10)."""

from __future__ import annotations

from ariane.attempts import AttemptTally
from ariane.runtime import (
    SessionResult,
    StopReason,
    as_int,
    cost_cap,
    is_token_cap,
    json_object,
    timeout_summary,
    token_cap,
)


def test_runtime_cap_texts() -> None:
    assert token_cap(5000) == "Ariane token cap (5000 tokens)"
    assert cost_cap(1.5) == "runtime cost cap (1.5 USD)"
    assert cost_cap(2.0) == "runtime cost cap (2 USD)"
    assert timeout_summary(90.0) == "killed after 90 s (time limit)"
    assert is_token_cap(token_cap(10))
    assert not is_token_cap(cost_cap(10))


def test_failed_result_and_usage_text() -> None:
    result = SessionResult.failed(StopReason.BUDGET, "x", cap=token_cap(3))
    assert result.input_tokens is None and result.cost_usd is None
    assert result.usage_text().startswith("Cap reached: Ariane token cap (3 tokens).\n\nCost not")
    assert SessionResult.failed(StopReason.ERROR, "x").usage_text().startswith("Cost not reported")


def test_parsing_helpers_and_call_id_dedup() -> None:
    assert json_object('{"a": 1}') == {"a": 1}
    assert json_object("[1]") is None and json_object("nope") is None
    assert as_int(True) is None and as_int(4) == 4 and as_int("4") is None
    tally = AttemptTally()
    tally.add_command("git push", "c1")
    tally.add_command("git push", "c1")
    assert tally.attempts.push == 1
