# Review 0

- Reviewed commit: `99c67f37fbd77faab4db4b63983239880fca22bf`
- Reviewer model: claude-opus-5-5
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`docs/architecture/modules/flow.md:42`) The flow workflow gets the fix-round loop and the exit codes wrong

  The diagram says `K{go and blocking checks green?} -- no --> fix session` and `Delivery.deliver --> Outcome exit 0`. The code does something else (src/ariane/flow.py:409-491). (1) When blocking checks fail on the first replay (round 0), the flow raises `Stop` ('blocking checks failed') with exit 1. It does not start a fix round. (2) The review runs only when the blocking checks are green (`if not failed:`). It does not run after every replay. (3) A delivery that ends in a draft returns `EXIT_STOPPED` (1), not 0. Only a ready pull request gives exit 0. This is the workflow of the module's main function and the main content this ticket delivers, so it gives readers a wrong picture of C10's core behaviour.

- **blocking** (`docs/architecture/modules/delivery.md:30`) The delivery workflow uses the wrong condition for a draft and leaves out a refusal

  The diagram decides a draft on 'blocking check red or review no-go?'. In the code, `Delivery.draft` is only `settled is not None and not settled.go` (src/ariane/delivery.py:97-100). A red blocking check with a `go` review gives a ready pull request, not a draft. The diagram also puts the draft decision after the push, but the code decides it first: it sets the status and commits the record before `_require_replayed` and the push. Finally, `PullRequestRefused` is also raised by `_require_replayed` before any push (delivery.py:102-114), and the diagram shows only the tracker's refusal.

- **minor** (`docs/architecture/modules/review.md:81`) `Settled.go` is a property, not a method

  The class diagram shows `go() bool`, but `go` is a `@property` (review.py:99-101). The Public API table says '`go` says whether it passes', which is fine. The same problem is in delivery.md: `draft() bool` is shown, but `Delivery.draft` is a property (delivery.py:97).

- **minor** (`docs/architecture/modules/git.md:98`) Code-view signatures are incomplete

  `commit(cwd, pathspec, message, env)` leaves out `tolerate_ignored`, and `push(cwd, url, sha, branch)` leaves out `token` and `environ`. The Public API table in the same file lists them. Many public functions (repo_root, fetch, diff, status, etc.) are missing from the class diagram. That is acceptable for a code view, but the signatures it does show should match the code.

- **minor** (`docs/architecture/modules/git.md:64`) The git workflow is a ticket overview, not the workflow of the module's functions

  The flowchart mixes the ticket's lifecycle ('agent runs under blocked_push_env') with the module's own `git()` error path. Placing `remote_refs` before and after at the end is misleading: refs_before is taken before the agent runs. It is still readable, but it describes how callers use the module more than the module itself.

- **blocking** Definition of done not met: The documentation the change affects is updated (C25).

  All 9 module files are rewritten to the template, and the 'docs: references' check passes. But the workflow diagrams of flow.md (fix-round loop, exit codes) and delivery.md (draft condition, refusal before the push) contradict src/ariane/flow.py:409-491 and src/ariane/delivery.py:52-114. The documentation is updated but not accurate.

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

  tests/test_docs_module_template.py:12-33 adds the 9 modules to `MIGRATED`. `test_c25_module_template_migrated_module_files_pass` would fail on the old `## Main types and functions` shape (missing sections, missing Public API names). I checked every top-level public name in the 9 sources with grep: each one has a row, and every row names something the code defines.

- **not met**: The documentation the change affects is updated (C25).

  All 9 module files are rewritten to the template, and the 'docs: references' check passes. But the workflow diagrams of flow.md (fix-round loop, exit codes) and delivery.md (draft condition, refusal before the push) contradict src/ariane/flow.py:409-491 and src/ariane/delivery.py:52-114. The documentation is updated but not accurate.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  The ticket applies the existing template of #124 / ADR 0039 without changing it or the test's rules. No new open choice is introduced, so no new ADR is needed.

## Proposed learnings (not decided)

- The module-template test only checks the Public API names and that the diagrams exist. Workflow diagrams need a manual check against the control flow, especially exit codes and loop conditions.
- Draw `@property` members as attributes in class diagrams, not as methods with `()`.
- For flow.md, check round 0 separately from fix rounds: on round 0, red blocking checks stop the ticket instead of starting a fix round.
