# 0023. A configurable definition of done

- Status: accepted
- Date: 2026-10-10
- Capabilities: C26, C10, C22, C25

## Context
The owner wants each project to say what "done" means for its tickets, and Ariane to hold
every ticket to it. Today "done" is implicit: green checks, and whatever the issue's acceptance
checklist says. Documentation upkeep (ADR 0022) is the first item that no check covers.

## Decision
- `ariane.toml` gains a `[definition_of_done]` table with an `items` list. Each item is either
  `{ check = "<name>" }`, naming a declared check (C9) that must pass, or
  `{ text = "<sentence>" }`, a requirement written for people. Without the table, Ariane uses a
  default list: every blocking check passes; the change is covered by tests that fail without
  it; the documentation the change affects is updated (C25).
- The implementer's prompt lists every item. The reviewer (C10) answers each sentence item with
  `met` or `not met` and its evidence, in its structured answer; an item not met counts as a
  blocking finding. Check items are verified by Ariane from the replay.
- A ticket's acceptance checklist adds items for that ticket; it never removes the project's.
- The pull request body and `work/<n>/review-*.md` list every item with its result.
- Delivery: configuration and prompt in a ticket before the reviewer; the item-by-item answer
  with the reviewer (#33). Until then, the owner's session checks the items by hand.

## Consequences
The reviewer's answer schema grows by one list. A project with no table gets the default, so
documentation upkeep applies everywhere. Items written as sentences are only as strict as the
reviewer reading them; anything mechanical belongs in a check.

## Alternatives considered
- A free text block in the prompt: nothing verifies it.
- Items only as checks: documentation and test quality cannot be checked by a command alone.
