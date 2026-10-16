# Review 1

- Reviewed commit: `91f4ca1bb77d03ac6d15bf7e9794141293bf661b`
- Reviewer model: claude-opus-5-5
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`docs/architecture/modules/git.md:72`) Workflow diagram reuses node ids K and L, so the push path is lost when rendered

  Lines 72-73 declare `K[push] --> L[push_env, one authenticated push, return the pushed commit]` and then `K[git args, cwd] --> L[run with safe options]`. In Mermaid the same id is one node and the last label wins. The rendered chart shows only 'git args, cwd' -> 'run with safe options', drawn twice. The `push`/`push_env` step, the single authenticated push that the module exists for (C11), does not appear at all. The other branches are also shown as linking into the GitError path. The ticket's deliverable is a correct workflow diagram, and the test only checks that a mermaid fence exists, so it cannot catch this. Fix: give the push branch its own ids (e.g. P[push] --> Q[...]) and keep K/L for the git runner.

- **minor** (`docs/architecture/modules/flow.md:79`) Code view shows `verify(...)` without its parameters

  `_TicketRun.verify` has the signature (after, start_commit, guard, refs_before, expected_head). The other methods in the code view list their parameters, but this one shows `...`. It is also a private class, so the module's public functions get less detail than the private class next to them.

- **minor** (`docs/architecture/modules/git.md:85`) Code view leaves out most public functions

  The classDiagram lists 13 of the 35 public functions; repo_root, fetch, diff, status, head and others are missing. The template does not require every function there, but the code view is noticeably less complete than the Public API table.

- **blocking** Definition of done not met: The documentation the change affects is updated (C25).

  All 9 module files are rewritten to the template. However, the git.md Workflow diagram (lines 72-73) reuses node ids K/L, so the push step drops out of the rendered diagram and the git-runner path is shown wrong. The documentation is therefore not yet correct.

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

  tests/test_docs_module_template.py adds the 9 modules to MIGRATED, so test_c25_module_template_migrated_module_files_pass now checks their sections, Public API rows and diagrams. The old '## Main types and functions' shape would fail it (missing sections). The public names I checked with grep in src/ariane/{git,delivery,flow,review,review_session,verify,replay,checks,stop}.py match the tables. The existing tmp_path tests cover a missing row.

- **not met**: The documentation the change affects is updated (C25).

  All 9 module files are rewritten to the template. However, the git.md Workflow diagram (lines 72-73) reuses node ids K/L, so the push step drops out of the rendered diagram and the git-runner path is shown wrong. The documentation is therefore not yet correct.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  The ticket fixes the template and the test rules (no change to either), and the change only applies the existing template from #124/ADR 0039. It makes no new design choice, so no ADR is needed.

## Proposed learnings (not decided)

- The module-template test only checks that a mermaid fence exists, not that the diagram is well-formed: reused node ids in a flowchart silently merge nodes. Reviewers should read the diagrams line by line, or a check could flag a node id defined with two different labels.
- When one Workflow diagram covers several independent entry points, give each sub-flow its own node-id prefix to avoid collisions.
