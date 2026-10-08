"""Redaction of known secrets and common token formats (C21)."""

from __future__ import annotations

import pytest

from ariane.redact import redact

GITHUB = "ghp_" + "a1B2c3D4e5" * 4
KEY_BLOCK = (
    "-----BEGIN OPENSSH PRIVATE KEY-----\nb3BlbnNzaC1rZXk\nAAAA\n-----END OPENSSH PRIVATE KEY-----"
)


@pytest.mark.parametrize(
    "secret",
    [
        "ghp_" + "a" * 30,
        "gho_" + "a" * 30,
        "ghu_" + "a" * 30,
        "ghs_" + "a" * 30,
        "ghr_" + "a" * 30,
        "github_pat_" + "A1_" * 8,
        "sk-ant-api03-" + "x" * 20,
        "sk-" + "Ab1" * 8,
        "AKIA" + "ABCD1234" * 2,
        "xoxb-1234567890-abc",
        "xoxp-1234567890",
    ],
)
def test_c21_redact_token_formats(secret: str) -> None:
    assert redact(f"before {secret} after") == "before *** after"


def test_c21_redact_known_secret_of_8_characters_or_more() -> None:
    assert redact("the value is hunter2hunter2!", ["hunter2hunter2!"]) == "the value is ***"


def test_c21_redact_known_value_shorter_than_8_is_left_untouched() -> None:
    assert redact("a short pass word", ["pass"]) == "a short pass word"


def test_c21_redact_private_key_block_is_masked_whole() -> None:
    assert redact(f"key:\n{KEY_BLOCK}\nend") == "key:\n***\nend"


def test_c21_redact_url_credentials() -> None:
    assert (
        redact("fatal: https://user:pw@github.com/o/r.git")
        == "fatal: https://***@github.com/o/r.git"
    )


def test_c21_redact_ordinary_text_is_left_untouched() -> None:
    text = (
        "commit 0123456789abcdef0123456789abcdef01234567 id 123e4567-e89b-12d3-a456-426614174000"
        " a skeleton task-list in https://github.com/o/r and AKIA1234"
    )
    assert redact(text) == text
