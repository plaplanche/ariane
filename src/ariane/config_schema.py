"""The description of `ariane.toml` as a JSON Schema, and the runtimes it allows (C22)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

CLAUDE_CODE = "claude-code"
OPENCODE = "opencode"
CODEX = "codex"
PI = "pi"
# Runtimes per role: opencode, codex and pi start with the reviewer (ADR 0029, 0043, 0051).
RUNTIMES = {"implementer": (CLAUDE_CODE,), "reviewer": (CLAUDE_CODE, OPENCODE, CODEX, PI)}
OPENCODE_TOOLS = ("read", "glob", "grep")
PI_TOOLS = ("read", "grep", "find", "ls")  # pi's read-only tools (not bash, edit, write)
REVIEWER_TOOLS = ("Read", "Glob", "Grep")
# The provider's own key variable, from pi's documented list (docs/providers.md, pi 0.73.1).
PI_PROVIDER_KEYS = {
    "anthropic": "ANTHROPIC_API_KEY",
    "azure-openai-responses": "AZURE_OPENAI_API_KEY",
    "openai": "OPENAI_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "google": "GEMINI_API_KEY",
    "mistral": "MISTRAL_API_KEY",
    "groq": "GROQ_API_KEY",
    "cerebras": "CEREBRAS_API_KEY",
    "cloudflare-ai-gateway": "CLOUDFLARE_API_KEY",
    "cloudflare-workers-ai": "CLOUDFLARE_API_KEY",
    "xai": "XAI_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "vercel-ai-gateway": "AI_GATEWAY_API_KEY",
    "zai": "ZAI_API_KEY",
    "opencode": "OPENCODE_API_KEY",
    "opencode-go": "OPENCODE_API_KEY",
    "huggingface": "HF_TOKEN",
    "fireworks": "FIREWORKS_API_KEY",
    "kimi-coding": "KIMI_API_KEY",
    "minimax": "MINIMAX_API_KEY",
    "minimax-cn": "MINIMAX_CN_API_KEY",
    "xiaomi": "XIAOMI_API_KEY",
    "xiaomi-token-plan-cn": "XIAOMI_TOKEN_PLAN_CN_API_KEY",
    "xiaomi-token-plan-ams": "XIAOMI_TOKEN_PLAN_AMS_API_KEY",
    "xiaomi-token-plan-sgp": "XIAOMI_TOKEN_PLAN_SGP_API_KEY",
}


def agent_problem(
    role: str,
    runtime: str,
    model: str,
    tools: Sequence[str],
    api_key_env: str | None,
    max_tokens: bool,
) -> tuple[str, str] | None:
    """The first rule of its runtime an `[agents.<role>]` table breaks, as (key, message), or
    None (C10, ADR 0029, ADR 0043, ADR 0051). `max_tokens`: whether the table sets it."""
    if api_key_env is not None and runtime not in (CODEX, PI):
        return "api_key_env", 'only with runtime "codex" or "pi"'
    if api_key_env is not None and not max_tokens:
        return "max_tokens", "required with api_key_env (a per-token session needs a token cap)"
    if runtime in (OPENCODE, PI):
        allowed = OPENCODE_TOOLS if runtime == OPENCODE else PI_TOOLS
        unknown = [t for t in tools if t not in allowed]
        if unknown:
            return (
                "tools",
                f"{unknown[0]!r} is not an allowed {runtime} tool ({', '.join(allowed)})",
            )
        problem = model_problem(runtime, model, api_key_env)
        if problem is not None:
            return "model", problem
        if not max_tokens:  # neither caps its own cost
            reason = f"{runtime} does not cap its own cost; Ariane needs a token cap"
            return "max_tokens", f"required with {runtime} ({reason})"
    elif role == "reviewer":
        other = [t for t in tools if t not in REVIEWER_TOOLS]
        if other:
            allow = ", ".join(REVIEWER_TOOLS)
            return (
                "tools",
                f"{other[0]} is not allowed (the reviewer's tools are an allow list: {allow}; C10)",
            )
    if "Skill" in tools:
        return "tools", "Skill is not allowed (undeclared skills, C6)"
    return None


def model_problem(runtime: str, model: str, api_key_env: str | None) -> str | None:
    """opencode and pi want `<provider>/<model>`; with `api_key_env`, pi passes the key under the
    provider's own variable, so the provider must be one pi documents (ADR 0051)."""
    if runtime not in (OPENCODE, PI):
        return None
    provider, _, name = model.partition("/")
    if not provider or not name:
        return f"{runtime} wants <provider>/<model>"
    if runtime == PI and api_key_env is not None and provider.lower() not in PI_PROVIDER_KEYS:
        return (
            f"api_key_env needs a provider whose key variable pi documents; {provider!r} is not"
            " one (or remove api_key_env and use pi's login)"
        )
    return None


_STR: dict[str, Any] = {"type": "string", "minLength": 1}
_ARGV: dict[str, Any] = {"type": "array", "minItems": 1, "items": _STR}
_POSITIVE: dict[str, Any] = {"type": "number", "exclusiveMinimum": 0}

_AGENT: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["runtime", "model", "tools", "max_budget_usd", "timeout_minutes"],
    "properties": {
        "runtime": {"enum": [CLAUDE_CODE, OPENCODE, CODEX, PI]},
        "model": _STR,
        "tools": {**_ARGV, "description": "Tools the agent may use (not Skill)."},
        "max_budget_usd": _POSITIVE,
        "max_tokens": {
            "type": "integer",
            "exclusiveMinimum": 0,
            "description": "Cap on tokens counted by Ariane per session;"
            " required when runtime is opencode or pi.",
        },
        "timeout_minutes": _POSITIVE,
        "idle_minutes": {
            **_POSITIVE,
            "description": "Stop the session when no event arrives for this many minutes; below"
            " timeout_minutes. Default 10, or none when timeout_minutes is 10 or less.",
        },
        "api_key_env": {
            **_STR,
            "description": "Codex or pi reviewer only: variable holding an API key, passed to the"
            " session as CODEX_API_KEY (Codex) or as the model provider's own key variable (pi);"
            " without it the CLI's own login is used.",
        },
    },
}

# A small change's reviewer settings (ADR 0046): runtime and tools stay the reviewer's.
_SMALL: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["max_lines"],
    "description": "Settings replacing the reviewer's for a change of at most max_lines changed"
    " lines (added plus deleted, without work/; a binary file counts 0); the prompt asks for a"
    " narrower review. The model, when given, differs from the implementer's (C10).",
    "properties": {
        "max_lines": {"type": "integer", "exclusiveMinimum": 0},
        "model": _STR,
        "max_budget_usd": _POSITIVE,
        "max_tokens": {"type": "integer", "exclusiveMinimum": 0},
        "timeout_minutes": _POSITIVE,
    },
}

# Only a role that may run on opencode or pi requires `max_tokens` for it.
_NEEDS_TOKENS: dict[str, Any] = {
    "if": {
        "type": "object",
        "properties": {"runtime": {"enum": [OPENCODE, PI]}},
        "required": ["runtime"],
    },
    "then": {"type": "object", "required": ["max_tokens"]},
}

# A pi reviewer may only read (ADR 0051).
_PI_REVIEWER_TOOLS: dict[str, Any] = {
    "if": {
        "type": "object",
        "properties": {"runtime": {"const": PI}},
        "required": ["runtime"],
    },
    "then": {
        "type": "object",
        "properties": {
            "tools": {
                "type": "array",
                "items": {"enum": list(PI_TOOLS)},
                "description": "A pi reviewer: read, grep, find, ls only",
            }
        },
    },
}

# A Claude Code reviewer may only read (ADR 0031).
_CLAUDE_REVIEWER_TOOLS: dict[str, Any] = {
    "if": {
        "type": "object",
        "properties": {"runtime": {"const": CLAUDE_CODE}},
        "required": ["runtime"],
    },
    "then": {
        "type": "object",
        "properties": {
            "tools": {
                "type": "array",
                "items": {"enum": list(REVIEWER_TOOLS)},
                "description": "A Claude Code reviewer: Read, Glob, Grep only",
            }
        },
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
                "env": {
                    "type": "array",
                    "items": _STR,
                    "default": [],
                    "description": "Variables agents, checks and setup commands receive beyond"
                    " the base set (ADR 0024); an entry ending in _ is a prefix.",
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
                "ready_label": {
                    **_STR,
                    "default": "ariane",
                    "description": (
                        "Label a person with write access puts on an issue to let Ariane run it."
                    ),
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
                    "properties": {**_AGENT["properties"], "small": _SMALL},
                    "allOf": [_NEEDS_TOKENS, _CLAUDE_REVIEWER_TOOLS, _PI_REVIEWER_TOOLS],
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
                    "setup": {
                        **_ARGV,
                        "description": "Replaces project.setup in this check's replay tree.",
                    },
                    "not_run_locally": {
                        "type": "array",
                        "minItems": 1,
                        "items": _STR,
                        "description": (
                            "Path globs of the files whose tests this check skips when Ariane"
                            " replays it (only CI runs them)."
                        ),
                    },
                },
            },
        },
    },
}
