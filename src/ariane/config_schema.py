"""The description of `ariane.toml` as a JSON Schema, and the runtimes it allows (C22)."""

from __future__ import annotations

from typing import Any

CLAUDE_CODE = "claude-code"
OPENCODE = "opencode"
# Runtimes per role: opencode starts with the reviewer (ADR 0029).
RUNTIMES = {"implementer": (CLAUDE_CODE,), "reviewer": (CLAUDE_CODE, OPENCODE)}
OPENCODE_TOOLS = ("read", "glob", "grep")


_STR: dict[str, Any] = {"type": "string", "minLength": 1}
_ARGV: dict[str, Any] = {"type": "array", "minItems": 1, "items": _STR}
_POSITIVE: dict[str, Any] = {"type": "number", "exclusiveMinimum": 0}

_AGENT: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["runtime", "model", "tools", "max_budget_usd", "timeout_minutes"],
    "properties": {
        "runtime": {"enum": [CLAUDE_CODE, OPENCODE]},
        "model": _STR,
        "tools": {**_ARGV, "description": "Tools the agent may use (not Skill)."},
        "max_budget_usd": _POSITIVE,
        "max_tokens": {
            "type": "integer",
            "exclusiveMinimum": 0,
            "description": "Optional cap on tokens counted by Ariane per session.",
        },
        "timeout_minutes": _POSITIVE,
    },
}

# Description of `ariane.toml` for docs/reference/ariane.toml.schema.json (ADR 0022). Keep it in
# step with `parse`: a test validates both example files against it.
SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "ariane.toml",
    "description": "Configuration of Ariane for one repository.",
    "type": "object",
    "additionalProperties": False,
    "required": ["project", "tracker", "agents", "checks"],
    "properties": {
        "project": {
            "type": "object",
            "additionalProperties": False,
            "required": ["base_branch"],
            "properties": {
                "base_branch": {**_STR, "description": "Branch the pull requests target."},
                "setup": {
                    **_ARGV,
                    "description": "Command run once in the working tree (list of arguments).",
                },
            },
        },
        "tracker": {
            "type": "object",
            "additionalProperties": False,
            "required": ["kind", "repository", "token_env"],
            "properties": {
                "kind": {"enum": ["github"]},
                "repository": {**_STR, "description": "owner/name"},
                "token_env": {**_STR, "description": "Environment variable holding the token."},
                "api_url": {
                    **_STR,
                    "default": "https://api.github.com",
                    "description": "https URL (plain http only to the local machine).",
                },
            },
        },
        "agents": {
            "type": "object",
            "additionalProperties": False,
            "required": ["implementer", "reviewer"],
            "properties": {
                "implementer": {
                    **_AGENT,
                    "properties": {**_AGENT["properties"], "runtime": {"enum": [CLAUDE_CODE]}},
                },
                "reviewer": {
                    **_AGENT,
                    "description": "Read-only reviewer (C10); model differs from the implementer.",
                },
            },
        },
        "definition_of_done": {
            "type": "object",
            "additionalProperties": False,
            "description": "What a change must satisfy to be done (C26); optional.",
            "properties": {
                "items": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "oneOf": [
                            {
                                "type": "object",
                                "additionalProperties": False,
                                "required": ["check"],
                                "properties": {
                                    "check": {**_STR, "description": "Name of a declared check."}
                                },
                            },
                            {
                                "type": "object",
                                "additionalProperties": False,
                                "required": ["text"],
                                "properties": {
                                    "text": {**_STR, "description": "A sentence to satisfy."}
                                },
                            },
                        ]
                    },
                    "description": "Default: tests pass, tests cover the change, docs updated.",
                }
            },
        },
        "documentation": {
            "type": "object",
            "additionalProperties": False,
            "description": "The project's documentation (C25); optional.",
            "properties": {
                "paths": {
                    **_ARGV,
                    "description": "Documentation files and folders, for `ariane docs-review`.",
                },
                "map": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["source", "docs"],
                        "properties": {
                            "source": {**_STR, "description": "Glob of source files."},
                            "docs": {
                                **_ARGV,
                                "description": "Documents covering them; {stem} is the matched"
                                " file's name without extension.",
                            },
                        },
                    },
                },
                "generated": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["name", "check"],
                        "properties": {
                            "name": {
                                **_STR,
                                "description": "Unique name; the check is `docs: <name>`.",
                            },
                            "check": {
                                **_ARGV,
                                "description": "Command exiting non-zero when a generated"
                                " document is stale (list of arguments).",
                            },
                        },
                    },
                },
            },
        },
        "checks": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["name", "command"],
                "properties": {
                    "name": {**_STR, "description": "Unique name of the check."},
                    "command": {**_ARGV, "description": "Command to run (list of arguments)."},
                    "blocking": {"type": "boolean", "default": True},
                    "timeout_minutes": {**_POSITIVE, "default": 15},
                },
            },
        },
    },
}
