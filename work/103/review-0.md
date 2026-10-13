# Review 0

- Reviewed commit: `34104172755fe62b72b53c20c74821a549183bd0`
- Reviewer model: claude-opus-5-5
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`docs/architecture/modules/runtime.md:8`) Module docs of touched modules `runtime` and `config_schema` not updated

  The change adds `Session.add_dirs` (src/ariane/runtime.py:32), which now sets the reviewer's cwd and the trees it may read. It also adds `REVIEWER_TOOLS` and a new `tools` description in src/ariane/config_schema.py. runtime.md:8 still describes `Session` without `add_dirs`, and config_schema.md:8 still lists only `RUNTIMES` and `OPENCODE_TOOLS`. Ariane flagged both documents as untouched. CLAUDE.md rule 11 and ADR 0022 require the `modules/<module>.md` of every module touched to be updated in the same ticket, so the C25 definition-of-done item is not met. Also add ADR 0031 to their 'Serves' lines.

- **minor** (`src/ariane/config_schema.py:28`) Schema does not express the reviewer allow list, and its description sits on both roles

  The `_AGENT` tools description ('a reviewer: Read, Glob, Grep only') is shared by implementer and reviewer, and it reads wrongly for an opencode reviewer, whose tools are `read`, `glob`, `grep`. The schema still accepts `WebFetch` for a Claude Code reviewer while `config.parse` refuses it. config_schema.md says a test checks that the schema and the parser agree; this rule is now a silent divergence. Consider an `if`/`then` on the reviewer (runtime claude-code ⇒ tools items enum Read/Glob/Grep), like the `max_tokens` rule.

- **minor** (`src/ariane/flow.py:515`) Stale `<n>-review` tree is not checked like the replay tree

  `_replay` refuses with a clear Stop when `<n>-replay` already exists (flow.py:480). `_review` calls `git.add_reviewer_worktree` directly, so a tree left by a crash makes git fail with a raw error. `verify` does have the check (verify.py:184). Add the same `exists()` guard.

- **minor** (`tests/test_c10_reviewer_isolation.py:76`) The '(none)' prompt case is not tested end to end

  `test_c10_reviewer_isolation_prompt_has_none_without_a_base_claude_md` only checks that `git.base_instructions` returns an empty string. Nothing asserts that the reviewer's prompt shows '(none)' under 'Project instructions (from the base branch)' and has no `project-instructions` tag.

- **minor** (`src/ariane/git.py:142`) Instruction-file removal is case-sensitive

  Names are compared exactly (`CLAUDE.md`, `AGENTS.md`, `.claude`). On case-insensitive file systems (Windows and macOS, the owner's platform), a committed `claude.md` or `Agents.md` may still be found and loaded by the agent CLI. Consider comparing with `casefold()`.

- **minor** (`src/ariane/review_session.py:67`) Empty cwd under the system temp dir: ancestors are writable by the implementer

  Claude Code loads `CLAUDE.md` from the ancestors of its cwd. The empty folder is created under the system temp dir, and an implementer running with bypassPermissions can write a `CLAUDE.md` into that temp dir before the reviewer starts. The OS sandbox is out of scope (slice 9), but record this residual vector in ADR 0031's consequences, or create the empty folder under a location Ariane controls.

- **blocking** Definition of done not met: The documentation the change affects is updated (C25).

  The new ADR 0031, the ADR 0029 amendment, the README, the regenerated schema and the module docs claude_code, config, review, review_session, git, flow and verify are updated. runtime.md (new `Session.add_dirs`) and config_schema.md (new `REVIEWER_TOOLS`) are not, though both modules changed.

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

  tests/test_c10_reviewer_isolation.py has 7 named tests (one parametrized four ways): instruction files are absent from the reviewer tree at depth while the replay tree keeps them; reviewer argv has `--restricted` and `--add-dir`, no bypassPermissions and no setting-sources; the implementer argv is unchanged; the reviewer runs from an empty cwd; WebFetch, Task, Bash and Write are refused; the prompt holds the base branch's CLAUDE.md and not the branch's. test_review.py was adapted to `add_dirs`. Each of these would fail on the base commit.

- **not met**: The documentation the change affects is updated (C25).

  The new ADR 0031, the ADR 0029 amendment, the README, the regenerated schema and the module docs claude_code, config, review, review_session, git, flow and verify are updated. runtime.md (new `Session.add_dirs`) and config_schema.md (new `REVIEWER_TOOLS`) are not, though both modules changed.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  docs/adr/0031-reviewer-isolation.md records the decision, the probe and the alternatives. It also records the open choices: the `-reviewer` suffix in verify, `Session.add_dirs`, and opencode keeping the tree as its cwd. ADR 0029's amendment points to it.

## Proposed learnings (not decided)

- When a change adds a field to a shared dataclass (for example `Session`) or a constant to a module, update that module's own doc, not only the docs of the modules that use it.
- A validation rule added to `config.parse` should also be stated in the generated JSON Schema, or the schema and the parser drift apart.
- Every temporary worktree Ariane creates needs the same 'already exists' guard; copy it from the replay tree.
