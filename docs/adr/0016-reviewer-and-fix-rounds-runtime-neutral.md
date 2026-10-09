# 0016. Reviewer session and fix rounds, on the runtime-neutral contract

- Status: accepted
- Date: 2026-10-08
- Capabilities: C10, C5, C21, C23

## Context
ADR 0010 relied on Claude Code's `--json-schema` for the validity of the reviewer's answer.
ADR 0015 makes Ariane enforce it for every runtime. ADR 0020 moves the learnings checkpoint
(ADR 0011) after the reviewer, and adds a command that verifies a branch done by hand.

## Decision
Everything in ADR 0010 stands except what follows.

**Answer**: the reviewer answers with the same object (`verdict`, `findings`, `learnings`).
Ariane parses and validates it itself against that schema (ADR 0015): with Claude Code it reads
`structured_output` when `--json-schema` is used; with a runtime without schema support it asks
for one fenced JSON block and parses it. An answer that does not validate is retried once in a
new session with the validation error; a second invalid answer stops the ticket with status
`needs a human`. `go` with a blocking finding counts as `no-go`.

**Where the reviewer reads**: in the clean working tree of the delivered commit (ADR 0018),
not in the implementer's working tree, so files the implementer left ignored by git cannot
influence it. Its tools are read-only (`Read`, `Glob`, `Grep`, or the runtime's equivalent
permissions), and Ariane verifies afterwards that nothing changed (git, tree, remote).

**Learnings**: until the learnings checkpoint ships (ADR 0020), the `learnings` field is
recorded in the review file and not decided; the pull request is pushed once after the review.

**Runtime**: the reviewer role first runs on Claude Code (model `claude-opus-5-5`, a different
model from the implementer's), then on opencode (ADR 0014), each with its adapter. The
configuration names the reviewer's runtime and model; Ariane refuses a reviewer model equal to
the implementer's.

**Branches done by hand**: `ariane verify <branch>` runs the same verification on a branch the
human finished (after a second `no-go`, or a ticket Ariane cannot run): clean-tree replay of
the checks (ADR 0018), one review, the review record committed to the branch, and a one-line
result. It never pushes; the human pushes and opens the pull request.

This decision supersedes ADR 0010.

## Consequences
The reviewer works the same on any runtime that passes ADR 0015's contract. One extra session
may run when an answer is invalid. The hand-takeover path gets the same evidence as Ariane's
own tickets.

## Alternatives considered
- Trust the runtime's schema validation: it does not exist on opencode, and a guarantee must
  not depend on a vendor flag (ADR 0014).
- Review in the implementer's working tree: ignored files there are invisible in the diff but
  visible to the reviewer.
