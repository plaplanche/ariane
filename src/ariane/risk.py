"""The risk tier of a round (C9, ADR 0056): the `[checks_policy]` table and the tier it gives."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

TIER_VARIABLE = "ARIANE_RISK_TIER"
FULL_SUITE_VARIABLE = "ARIANE_FULL_SUITE"
LOW = "low"
HIGH = "high"
FULL_WHEN = (HIGH, "always")  # `checks[].full_when`: when the check gets ARIANE_FULL_SUITE=1
NO_POLICY = "no `[checks_policy]`"
DEFAULT_MAX_CHANGED_LINES = 300
DEFAULT_MAX_MODULES = 3
_KEYS = ("max_changed_lines", "max_modules", "module_roots", "critical_paths")


class PolicyError(ValueError):
    """The `[checks_policy]` table is invalid; the message names the key."""


@dataclass(frozen=True)
class ChecksPolicy:
    """`[checks_policy]`: what makes a round `high`. `module_roots` are globs of the folders
    whose children count as modules; empty, the repository root is the only one."""

    max_changed_lines: int = DEFAULT_MAX_CHANGED_LINES
    max_modules: int = DEFAULT_MAX_MODULES
    module_roots: tuple[str, ...] = ()
    critical_paths: tuple[str, ...] = ()


@dataclass(frozen=True)
class Tier:
    """A round's tier, `low` or `high`, and why. `measured` is False without `[checks_policy]`:
    the tier is then `high` and changes nothing else (the review keeps its sizing by lines)."""

    level: str
    reasons: tuple[str, ...]
    measured: bool = True

    @property
    def high(self) -> bool:
        return self.level == HIGH

    def text(self) -> str:
        """`high: 412 changed lines (more than 300); touches `critical_paths` `src/auth/**``."""
        return f"{self.level}: {'; '.join(self.reasons)}"

    def variables(self, full_when: str) -> dict[str, str]:
        """`ARIANE_RISK_TIER`, and `ARIANE_FULL_SUITE` for a check with this `full_when`."""
        full = self.high or full_when == "always"
        return {TIER_VARIABLE: self.level, FULL_SUITE_VARIABLE: "1" if full else "0"}


UNMEASURED = Tier(HIGH, (NO_POLICY,), measured=False)


def parse(raw: Any) -> ChecksPolicy | None:
    """The `[checks_policy]` table, or None without it; a PolicyError names the faulty key."""
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise PolicyError("checks_policy: expected a table")
    for key in raw:
        if key not in _KEYS:
            raise PolicyError(f"checks_policy.{key}: unknown key")
    return ChecksPolicy(
        _count(raw, "max_changed_lines", DEFAULT_MAX_CHANGED_LINES),
        _count(raw, "max_modules", DEFAULT_MAX_MODULES),
        _globs(raw, "module_roots"),
        _globs(raw, "critical_paths"),
    )


def _count(raw: dict[str, Any], key: str, default: int) -> int:
    value = raw.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise PolicyError(f"checks_policy.{key}: expected a positive integer")
    return value


def _globs(raw: dict[str, Any], key: str) -> tuple[str, ...]:
    if key not in raw:
        return ()
    value = raw[key]
    if not isinstance(value, list) or not value or not all(isinstance(v, str) and v for v in value):
        raise PolicyError(f"checks_policy.{key}: expected a non-empty list of path globs")
    return tuple(value)
