# Review 1

- Reviewed commit: `ff8f9dd6f6d772036071021d9e014d1fc97820bc`
- Reviewer model: claude-opus-5-5
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`docs/architecture/2-containers.md:34`) C4 container view still describes the old, unsafe reviewer setup

  Line 34 still says "The reviewer session is read-only: its tools exclude writing and it runs in a clean replay tree", and line 25 labels the edge "reviewer: read-only, in a replay tree". After this change both claims are wrong, and they describe the exact security property the ticket is about: the tools are now an allow list (Read, Glob, Grep) and the reviewer reads a separate tree with no CLAUDE.md, AGENTS.md or .claude/, from an empty cwd. CLAUDE.md rule 11 and ADR 0022/0023 require the C4 level files to be updated in the same ticket.

- **blocking** (`docs/architecture/3-components.md:115`) Component sequence diagrams still say the reviewer runs in the replay tree

  Lines 115 (start flow) and 149 (verify flow) say "run a read-only reviewer session in the replay tree". They should now name the reviewer tree (`<n>-review` / `-reviewer`) that has no instruction files (ADR 0031). The module docs were updated, but the C4 component level, which rule 11 also requires, was not.

- **minor** (`docs/adr/0025-review-implementation.md:12`) ADR 0025 is superseded on where the reviewer runs, but has no pointer to ADR 0031

  ADR 0025 says the reviewer runs in the replay working tree. ADR 0031 changes this but lists only 0010, 0016 and 0029 under "Amends", and only 0029 got an amendment note. Add 0025 to the list (and ideally add back-pointers in 0010 and 0016).

- **minor** (`src/ariane/verify.py:182`) The `ariane verify` path to the reviewer tree is not tested

  No test checks that `ariane verify` gives the reviewer the `-reviewer` tree without instruction files, puts the base branch's CLAUDE.md in the prompt, or removes the tree afterwards. All the new isolation tests go through `ariane start` only. The opencode path (cwd = reviewer tree, no add_dirs) also has no isolation test.

- **minor** (`src/ariane/git.py:143`) Symlinks in the tree can still point to instruction files outside it

  `add_reviewer_worktree` deletes files and directories by name, but a committed symlink (for example `notes -> ../103`, the implementer's worktree, or another absolute path) stays in place. Reading through it could still make Claude Code load a CLAUDE.md from outside the tree. Consider removing or refusing symlinks that leave the tree, or recording this as a residual vector in ADR 0031 next to the temporary-directory one.

- **minor** (`src/ariane/flow.py:519`) A partly built reviewer tree blocks the next run

  If `add_reviewer_worktree` fails after `git worktree add` (for example the deletion fails), the call is outside the try/finally, so the tree is never removed. The next run then stops with "already exists". Putting the creation inside the try/finally, or cleaning up on failure, would avoid this.

- **minor** (`src/ariane/config_schema.py:28`) Unrelated change to the schema description

  "Tools the agent may use (not Skill)." lost its trailing period for no reason the ticket gives. This is harmless but adds noise to the regenerated reference.

- **blocking** Definition of done not met: The documentation the change affects is updated (C25).

  Updated: ADR 0031, the ADR 0029 amendment, README, the module docs (claude_code, config, config_schema, flow, git, review, review_session, runtime, verify) and the regenerated schema JSON. Not updated: docs/architecture/2-containers.md:25,34 and 3-components.md:115,149 still say the reviewer runs in the replay tree and that its tools exclude writing.

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

  tests/test_c10_reviewer_isolation.py has 8 test functions, one parametrized (11 cases). They cover: the tree without instruction files while the replay keeps them, the base branch's CLAUDE.md in the prompt, (none) when there is no base CLAUDE.md, case-insensitive removal, the restricted argv, the unchanged implementer argv, the empty cwd, and the allow list. test_docs_reference adds a schema test. All of these fail on the base code. Gap: the verify path has no test.

- **not met**: The documentation the change affects is updated (C25).

  Updated: ADR 0031, the ADR 0029 amendment, README, the module docs (claude_code, config, config_schema, flow, git, review, review_session, runtime, verify) and the regenerated schema JSON. Not updated: docs/architecture/2-containers.md:25,34 and 3-components.md:115,149 still say the reviewer runs in the replay tree and that its tools exclude writing.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0031 records the reviewer tree (including the `-reviewer` suffix used by verify), the restricted Claude Code flags, the tools allow list, the base branch's CLAUDE.md in the prompt and the temporary-directory residual vector. It does not list ADR 0025 among the ADRs it amends (minor).

## Proposed learnings (not decided)

- When a change moves where an agent session runs or what it may do, grep docs/architecture/*.md (the C4 level files) as well as modules/*.md: statements like 'runs in a clean replay tree' live in the container and component views.
- When an ADR changes behaviour that an earlier ADR describes, grep docs/adr for the old wording so the 'Amends' list is complete.
- Deleting instruction files by name does not handle symlinks that point outside the tree; record that residual vector or handle it.
