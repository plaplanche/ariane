# Review 1

- Reviewed commit: `fbef224180f0d794200252d456ee1abfff7ab80a`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/review.py:247`) A symlinked docs directory admits residuals absent from the base commit

  residuals_in checks whether docs/adr and each Markdown file are symlinks, but not whether docs is a symlink. If the base tracks docs as a link to an external directory containing adr/0001-example.md, these checks pass and read_text imports that external file's markers. The prompt then instructs the reviewer to downgrade matching findings as owner-accepted, although those contents were never committed or accepted. No concurrent mutation is needed: external file contents → residuals_in → authoritative downgrade rule. This breaks the ticket's base-commit trust boundary and differs from verify's Git-object reader. Reject linked ancestor directories or read committed blobs, and add a regression test asserting external residuals are excluded.

## Definition of done

- met: check lint passes

  Replayed by Ariane: exit 0.

- met: check format passes

  Replayed by Ariane: exit 0.

- met: check types passes

  Replayed by Ariane: exit 0.

- met: check tests passes

  Replayed by Ariane: exit 0.

- met: check file length passes

  Replayed by Ariane: exit 0.

- met: The change is covered by tests that fail without it.

  The 13 named tests exercise prompt rules, base-only residuals, configuration, matching and nonmatching paths, refused labels, GitHub requests, verify, and renames. Their assertions depend on the new behavior. Supplied replay reports tests passing; I did not rerun file-writing tests. The linked-ancestor case is missing. Delivery trace: journal/status writes → local record commit → replay and push guards → push → pushed journal → PR creation with sensitive-path notice → delivered journal → label POST or warning journal → commit statuses → final status and local record commit.

- met: The documentation the change affects is updated (C25).

  README, example configuration, configuration schema reference, log catalogue, component diagram, and affected module documentation are updated. The review-answer schema is unchanged. The supplied generated-reference check passed.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0057 records continuation parsing, base acquisition for start and verify, proportion exceptions, rename matching, label timing, refusal handling, and unchanged verdict settlement. The finding concerns implementation of the recorded base-only guarantee.

## Proposed learnings (not decided)

- Proposed: When filesystem content represents committed policy, validate every ancestor component; checking only the final directory and file does not exclude symlink traversal.
