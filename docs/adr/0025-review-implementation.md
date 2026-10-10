# 0025. Review implementation choices

- Status: accepted
- Date: 2026-10-10
- Capabilities: C10, C26

## Context
ADR 0016 fixes the review; a few details were left open.

## Decision
- `[agents.reviewer]` is required: every ticket is reviewed. The reviewer's model must differ from the implementer's, checked at load.
- The reviewer runs in the replay working tree, which is kept until the review ends. After each session Ariane checks the ticket branch, git configuration and remote as after any agent, and that the replay tree has the same head and the same `git status` as before; ignored files are not compared.
- The diff given to the reviewer runs from the commit where the ticket folder was opened to the replayed commit, without `work/`, cut at 200,000 characters.
- A sentence item is matched to the answer by its exact text (surrounding whitespace ignored). A check item is met when its replayed check passed.
- A reviewer session that does not finish, or edits the tree, stops the ticket as `needs a human`; so does a `no-go`.

## Consequences
A first review is `review-0.md`; fix rounds will add `review-1.md` and so on. Editing an ignored file in the replay tree is not detected.

## Alternatives considered
- Optional reviewer: rejected, C10 says every ticket.
- Fuzzy matching of items: rejected, an unmatched item is simply unmet, which is safe.
