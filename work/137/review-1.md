# Review 1

- Reviewed commit: `9299a66c05d103cababcfa0f5b74ba38b9cd954e`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/review_session.py:193`) Small opencode models inherit the wrong provider credentials

  The selected small model receives self.env, which was filtered using the default reviewer's provider. cli._runtime constructs OpenCodeRuntime(model=agent.model); flow and verify use that runtime's login_variables before selecting the small settings. With reviewer.model='anthropic/large' and small.model='openai/small', OPENAI_API_KEY is removed even when supplied, so the small review fails authentication unless separately logged in. A read-only reproduction confirmed that only ANTHROPIC_API_KEY survives. Resolve the login environment for the selected model in both paths, preserving credential isolation, and add cross-provider coverage.

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

  The new test module exercises configuration rejection, small versus large sessions, prompt compatibility, counting exclusions, metrics, cap guidance and verify. These assertions depend on the new behavior. Ariane reports the suite passed; I did not rerun filesystem-writing tests. Cross-provider authentication remains uncovered.

- met: The documentation the change affects is updated (C25).

  README, the commented example, generated schema and architecture documentation for all changed modules are updated.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0046 records line-based selection, inherited settings, model independence, idle-limit handling, cap guidance and records.

## Proposed learnings (not decided)

- Proposed: When model selection changes per session, test provider-specific credential filtering as well as the model argument.
- Review-path audit: worktree creation and instruction removal precede counting; temporary-folder creation and instruction/start logs precede the runtime call; session metrics and stop logs precede the guard; answer validation and any retry follow the guard. Settled review records follow validation. Verify additionally checks branch state before writing and committing final records. The added count is read-only and uses fixed commit IDs.
