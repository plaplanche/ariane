# Review 2

- Reviewed commit: `e1e3a4b8aae864087dd0515fb30a06cb271ae0f9`
- Reviewer model: claude-opus-5-5
- Verdict: **go**

## Findings

- **minor** (`docs/architecture/modules/flow.md:44`) Workflow shows setup after the ticket folder is opened, but the code runs it first

  In `_TicketRun.execute` (src/ariane/flow.py:162-172), `self.setup(self.worktree)` runs first. Then `self.folder.create(...)` opens the folder, and only after that is a setup error raised. The diagram draws 'open the ticket folder --> setup command'. It should show setup running before the folder exists, with its error raised (and journaled) after the folder is opened.

- **minor** (`docs/architecture/modules/delivery.md:9`) The FAILURES description does not match the code comment

  src/ariane/delivery.py:14 describes `FAILURES` as the failures that stop a ticket cleanly, with a journaled reason instead of a traceback. flow and verify use it for that. The table row says 'The exception types a delivery step can raise', which is narrower and misleading.

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

  tests/test_docs_module_template.py adds the 9 modules to `MIGRATED`. `test_c25_module_template_migrated_module_files_pass` then checks their section order, that the Public API table matches the public names from `ast`, and the Mermaid diagrams. The old-shape files (`## Main types and functions`) would fail this test. Existing tests on modules written in tmp_path already cover the 'missing public name' case. Ariane replayed the tests and they pass.

- met: The documentation the change affects is updated (C25).

  All 9 module files (checks, delivery, flow, git, replay, review, review_session, stop, verify) now follow the template. Their Public API tables match the code: the test passes, and I spot-checked the names and fields in delivery.py, review.py and flow.py. The template and src/ are unchanged, so no other architecture file, generated reference or README is affected. The 'docs: references' check passes.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  The ticket fixes the template ('no change to the template or to the test's rules'). The change applies the template from #124 and ADR 0039 and leaves no new choice open, so no new ADR is needed.

## Proposed learnings (not decided)

- When rewriting a module file's workflow diagram, check the step order against the main function's code (for example, flow's setup runs before the ticket folder is created). The template test checks names, not the order of steps in a diagram.
- A Public API row's description should paraphrase the docstring or comment in the code, so it stays accurate for every caller, not only the module being documented.
