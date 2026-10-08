"""Redaction (C21): known secrets and common token formats never leave Ariane unmasked."""

from __future__ import annotations

import re
from collections.abc import Iterable

MASK = "***"
MIN_SECRET_LENGTH = 8  # shorter known values would mask common words
_PATTERNS = (
    # Private key blocks come first, whole, so that nothing inside is masked piecemeal.
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.DOTALL),
    re.compile(r"\bgh[pousr]_\w{30,}"),
    re.compile(r"\bgithub_pat_\w{20,}"),
    re.compile(r"\bsk-ant-[\w-]{20,}"),
    re.compile(r"\bsk-[\w-]{20,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}(?![0-9A-Za-z])"),
    re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"),
)
_USERINFO = re.compile(r"(?i)\b([a-z][a-z0-9+.-]*://)[^/@\s]+@")


def redact(text: str, known: Iterable[str] = ()) -> str:
    """`text` with the known secrets, common token formats and URL credentials replaced."""
    for secret in sorted({s for s in known if len(s) >= MIN_SECRET_LENGTH}, key=len, reverse=True):
        text = text.replace(secret, MASK)
    for pattern in _PATTERNS:
        text = pattern.sub(MASK, text)
    return _USERINFO.sub(rf"\1{MASK}@", text)
