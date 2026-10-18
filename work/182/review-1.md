# Review 1

- Reviewed commit: `0f3245dadb348f38dccb28a16ff9cc5d49bad7ef`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/git.py:249`) Relative pi configuration paths bypass the instruction guard

  PI_CODING_AGENT_DIR is accepted and forwarded unchanged, but the guard resolves relative paths from Ariane's working directory while pi runs in the reviewer tree. With PI_CODING_AGENT_DIR=pi-config, the sequence is: the guard snapshots <repo>/pi-config; the implementer writes and commits pi-config/models.json; replay creates the reviewer tree and preserves that directory; pi loads <review-tree>/pi-config/models.json and can send its model request to the configured endpoint; metrics and journal entries are written; the post-session guard checks <repo>/pi-config again and misses the changed configuration. No concurrency is needed. A read-only probe confirmed that snapshot keys remain relative and the environment forwards the relative value. Resolve the directory once to an absolute path shared by the guard and subprocess, or reject relative values before setup. Add coverage for this case; existing tests use absolute paths.

- **minor** (`src/ariane/review_session.py:281`) The pi session journal omits its enforced dollar cap

  PiRuntime enforces max_budget_usd against reported cost, but cap_text records only max_tokens. The session-start journal therefore omits an active limit, including any small-review dollar override. Include both limits, as the opencode branch does, and test the displayed values.

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

  The new test_c5_pi suite exercises runtime routing, CLI arguments, credentials, usage, caps, process-tree termination, delivery and isolation. These depend on the new implementation. Ariane reports the suite green; I did not rerun tests that write files. Relative configuration paths remain untested.

- met: The documentation the change affects is updated (C25).

  README, the example configuration, generated schema, architecture views and affected module documents are updated. Ariane reports the generated-reference check green; no new log identifiers require catalogue changes.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0051 records stdin transport, authentication mapping, event fields, retry handling, cost accounting and isolation choices. ADR 0031 documents the additional guarded files and .pi removal.

## Proposed learnings (not decided)

- Proposed: normalize runtime configuration paths once before taking guard snapshots, and pass those same absolute paths to subprocesses running in other directories.
