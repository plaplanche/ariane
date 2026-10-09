# 0014. Ariane is an orchestrator in code, independent of one model vendor

- Status: accepted
- Date: 2026-10-08
- Capabilities: C5, C9, C10, C11, C21

## Context
An outside review of the repository asked whether Ariane should rather be a set of agent
instructions (skills, prompts, a CLAUDE.md workflow) run by a coding agent. It also noted that
slice 1 relies on one agent runtime and one vendor's models.

## Decision
- **Ariane stays an orchestrator written in code.** A gate enforced by code cannot be skipped;
  an instruction to an agent can. Every guarantee the spec states (checks replayed, review on a
  different model, no push by an agent, records the agent cannot forge) is enforced by Ariane's
  code around the agent, never by asking the agent to comply.
- **Independence from one model vendor is a requirement.** The agent runtime contract is
  runtime-neutral (ADR 0015). The second runtime, opencode, comes right after that contract,
  starting with the reviewer role (read-only), so that the review by a different model can
  also be a review by a different vendor.

## Consequences
New capabilities are built as code paths with tests, not as prompt text. A runtime feature
(a budget flag, a schema option) is used as an optimisation only; the guarantee stays in
Ariane (ADR 0015).

## Alternatives considered
- A skills-only workflow: cheaper to start, but every gate becomes a request the agent may
  ignore, and nothing verifies it afterwards.
- One vendor only: simpler, but the reviewer would share the implementer's blind spots and
  Ariane would stop when that vendor does.
