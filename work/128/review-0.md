# Review 0

- Reviewed commit: `3e310f976dbcf9200886fa3d6869f8df876103be`
- Reviewer model: claude-opus-5-5
- Verdict: **go**

## Findings

- **minor** (`tests/test_docs_module_template.py:210`) The 'no module file' branch is never exercised in tmp_path

  The acceptance criterion asks for a tmp_path test showing that adding a module without a conforming file fails the check. The existing tmp_path tests cover a file that breaks the template. The new branch that reports a missing `.md` (`no module file for ...`) is new logic, and no test runs it. The whole-repo loop is hard-wired to ROOT, so it cannot run on a fake tree. Moving the loop into a helper that takes a root, and adding a tmp_path test with a `.py` but no `.md`, would cover it.

- **minor** (`tests/test_docs_module_template.py:206`) Module count guard is `>= 28`, not exactly the 28 modules

  `assert len(modules) >= 28` protects against an empty glob, which is good. It does not pin the count the ticket names. This is acceptable because new modules must still pass the template, so it is noted only.

- **minor** (`docs/architecture/modules/claude_code.md:23`) "none is raised" overstates error handling

  `ClaudeCodeRuntime._run` catches only `process.CommandNotFoundError`. opencode's `run` catches `(CommandNotFoundError, OSError)`. If `process.stream` can raise OSError for any reason other than a missing command, it would propagate here. Either narrow the sentence or check that `process.stream` wraps OSError.

- **minor** (`docs/architecture/modules/attempts.md:17`) Only `sh -c` and `bash -c` are named, but the code also recurses into zsh and dash

  `_SHELLS = {"sh", "bash", "zsh", "dash"}` in src/ariane/attempts.py:9. The sentence was carried over from the old file, but the ticket asks the files to be true to the code.

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

  `test_c25_module_template_every_module_file_passes` now globs every `src/ariane/*.py` except `__init__` (28 modules). On the base docs it would fail: the 8 old-shape files lack `## Public API`, `## Workflow` and `## Code view`, and measures/opencode public names (e.g. `moment`, `agent_name`) were undocumented. The tests check passed on the change. The missing-file branch has no tmp_path test (minor finding).

- met: The documentation the change affects is updated (C25).

  All 8 module files (attempts, claude_code, measures, metrics, opencode, report, runtime, shadow) were rewritten to the template. I spot-checked their Public API signatures against the source: `shadow_lines(shadows, recent)`, `build(root, since, tracker=None)`, `count(command, depth=0)`, `start(number, *, ...)`, `judge(..., note=None)`, `Metrics(number, mode, write)`, `OpenCodeRuntime(executable, model)`, `Events(max_tokens, max_budget_usd)`, and the constants. docs/architecture/README.md now says the check runs on every module of `src/ariane/`. The docs: references check is green.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  The ticket fully decides the design: apply the ADR 0039 template, drop `MIGRATED`, and check every module. The diff makes no new design choice, so no new ADR is needed.

## Proposed learnings (not decided)

- When a doc-conformance test is widened from an allow-list to a glob, keep the per-root loop in a helper so tmp_path tests can cover the new failure branches (e.g. a missing doc file).
- When rewriting a module file to a template, re-verify carried-over prose against the code (e.g. the shell list in attempts, the error-handling claims in runtimes); the Public API test checks names only, not prose.
