# Review 0

- Reviewed commit: `eb6c3971f748e581cf667d147f13c58ffbdd0d84`
- Reviewer model: claude-opus-5-5
- Verdict: **go**

## Findings

- **minor** (`README.md:11`) "Measurement and approvals come next" merges two slices

  In the spec roadmap (docs/spec.md:388-389), slice 4 is "Measurement and shadow" and approvals come in slice 5. The sentence is not wrong, but "Measurement and shadow mode come next" would match the roadmap more closely.

- **minor** (`README.md:82`) Capability range C1 to C24 is out of date (not part of this diff)

  The spec and this README both use C25 and C26, but line 82 still says "capabilities C1 to C24" (docs/spec.md:17 says the same). This line was not changed here; it is worth fixing in a later documentation pass.

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

  Not applicable: the change only touches the README status paragraph and changes no behaviour, so no test can fail without it. The replayed checks, including docs: references, are green.

- met: The documentation the change affects is updated (C25).

  The change is the documentation update. The new status matches the roadmap's slice 3 row (docs/spec.md:387): fix rounds (C10), clean-tree replay, the reviewer on opencode (src/ariane/opencode.py) and `ariane verify` (src/ariane/verify.py). It also matches the rest of the README (lines 40-78).

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  The README wording change introduces no design choice, so no ADR is needed.

## Proposed learnings (not decided)

- When a README status line is updated for a new slice, check its wording against the spec's roadmap table so the 'comes next' text names the next slice exactly.
- Keep the capability ranges quoted in docs ("C1 to C24") in step with the spec when new capabilities (C25, C26) are added.
