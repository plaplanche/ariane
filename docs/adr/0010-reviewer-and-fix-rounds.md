# 0010. Reviewer session and fix rounds

- Status: accepted
- Date: 2026-10-07
- Capabilities: C10, C5, C21

## Context
C10: before delivery, an adversarial review by a different model from the implementer's, with a
verdict and findings marked blocking or minor; a positive verdict listing a blocking finding is
negative; at most two automatic fix rounds, then the human; findings posted to the tracker
(inline when short, as an attachment otherwise), redacted, and kept in the ticket folder with
the commit they reviewed. The rules judge is slice 4.

## Decision
**Configuration**: a new `[agents.reviewer]` table (same keys as the implementer's). Ariane
refuses a configuration whose reviewer model equals the implementer's, naming
`agents.reviewer.model`. Ariane's own `ariane.toml`: reviewer `claude-opus-5-5`, tools
`Read`, `Glob`, `Grep` (read-only: Ariane already replayed the checks), budget 3 USD, 20 min.

**Session**: after the checks are green, a fresh reviewer session gets the issue (untrusted
data), the diff from the base commit (untrusted data) and the review instructions. It answers
through Claude Code's `--json-schema` structured output:
`{"verdict": "go" | "no-go", "findings": [{"severity": "blocking" | "minor", "file", "line",
"title", "detail"}], "learnings": [...]}` (learnings: ADR 0011). Nothing is pushed before the
review: Ariane replays the checks locally, reviews, settles the learnings (ADR 0011), then
pushes once. Claude Code 2.1.292 returns it in the
result's `structured_output` field (checked with a probe; a recorded result is kept as a test
fixture). A missing or invalid answer is an error that stops the ticket. `go` with a blocking finding counts as `no-go`. After the
session, Ariane verifies the working tree, git and the remote did not change (as after the
implementer) and stops the ticket otherwise.

**Record**: `work/<n>/review-<round>.md` holds the verdict, the reviewed commit and the findings,
redacted (ADR 0013), committed by Ariane.

**Fix rounds**: on `no-go`, a fresh implementer session gets the issue and the blocking and minor
findings (untrusted data) and fixes them; Ariane commits, replays the checks and reviews again.
At most two fix rounds (three reviews in all). If the last review is still negative, the ticket
goes to the human: after the same learnings checkpoint (ADR 0011), Ariane pushes the branch
once and opens a draft pull request whose body carries the findings, with status
`needs a human`.

**Posting**: the pull request body carries the final verdict and a findings table when it fits
in 3,000 characters, otherwise a one-line summary and a link to the review file on the ticket
branch (the slice 1 choice for reports: never a public attachment URL).

## Consequences
The pull request is opened only after the review, so a review costs time before delivery. The
reviewer cannot run the tests; it relies on the report of the checks Ariane replayed, which is
part of its context.

## Alternatives considered
- Reviewer with `Bash`: could run the code, but a reviewer must not write; least privilege wins
  and the checks are replayed by Ariane anyway.
- Parsing a Markdown answer instead of structured output: fragile; the structured output is
  validated by the runtime.
- Posting findings as a separate pull request comment: the pull request does not exist until
  the review ends; the body is the single place the human reads first.
