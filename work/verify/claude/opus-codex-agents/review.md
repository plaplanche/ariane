# Review 0

- Reviewed commit: `6f2ce1caf4eb07a914e717a5061a92c1f8f6f30e`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`ariane.toml:30`) Token cap does not bound the newly enabled API-billed review

  An API-key CLI login is accepted. The execution order is: write review-start log; check login; launch Codex and incur API charges; receive turn.completed; check max_tokens; stop the process; record metrics and review-stop log. src/ariane/codex.py only counts usage at turn.completed, and its command supplies no native token cap. Consequently, an entire review turn can exceed 2,000,000 tokens before the check runs; max_budget_usd is also unused by this runtime. An in-memory reproduction reported 3,001,000 tokens before triggering the configured 2,000,000-token cap. This contradicts ADR 0044's billing bound and C5's requirement for a native cap when usage arrives only at the end. Require a plan login for this configuration or enforce a runtime-supported spending bound before allowing API-billed execution. Add a test covering consumption before turn completion; the existing test only kills a fake process hanging after completion.

- **minor** (`docs/adr/0044-opus-implements-codex-reviews.md:12`) Login prerequisite contradicts the accepted API-key fallback

  This sentence says that without a ChatGPT login the ticket stops with 'Codex is not logged in', but an existing API-key login proceeds, as the following sentence and runtime explicitly establish. State that only an absent login causes this error. Update the README's Codex setup guidance to explain the same distinction.

- **blocking** Definition of done not met: The documentation the change affects is updated (C25).

  ADR 0044 and configuration comments document the switch, but claim an unenforced billing bound and contain contradictory login guidance. The README does not incorporate the API-key-login clarification.

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

  The new configuration assertions pass on this checkout and fail against the base configuration's Sonnet implementer and Claude reviewer. Ariane reports all replayed tests passing. This coverage does not establish the claimed spending bound.

- **not met**: The documentation the change affects is updated (C25).

  ADR 0044 and configuration comments document the switch, but claim an unenforced billing bound and contain contradictory login guidance. The README does not incorporate the API-key-login clarification.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0044 records the implementer model and budget, reviewer runtime and model, CLI login policy, token threshold, and alternatives.

## Proposed learnings (not decided)

- A usage threshold checked after a completed agent turn cannot guarantee a spending bound within that turn.
- Test billing safeguards at the point charges occur, rather than only testing termination after usage is reported.
