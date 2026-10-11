# Review 0

- Reviewed commit: `6718d8a112f200a9c42525abe23ad65393038395`
- Reviewer model: claude-opus-5-5
- Verdict: **go**

## Findings

- **minor** (`docs/adr/0029-opencode-reviewer.md:14`) ADR 0029 not amended with the --dir / PWD finding

  ADR 0029 records how the opencode reviewer is started (stdin, flags, amended once already). The new fact that opencode resolves its project directory from PWD rather than the process cwd, and the decision to pass --dir plus PWD, is recorded only in the module doc. An 'amended' line in ADR 0029 would keep the decision record complete. This is not blocking: the ticket fixed the decision itself, so it is not a choice the spec leaves open.

- **minor** (`tests/test_c5_opencode.py:138`) The new test checks command() and environment() directly, not what the spawned process receives

  test_c5_opencode_dir_* calls adapter.command/adapter.environment rather than going through run() with fake_opencode.py, which dumps argv/env. The updated len(argv) == 10 assertion in the end-to-end test partly covers this, but it does not check that argv[8:10] == ['--dir', str(tmp_path.resolve())] or that env['PWD'] reached the child. Adding those two assertions would make the end-to-end test cover it too.

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

  tests/test_c5_opencode.py:138 test_c5_opencode_dir_is_the_session_tree_in_the_command_and_in_pwd: without the change, command.index('--dir') raises ValueError, and PWD would remain '/somewhere/else' (the base env sets a stale PWD). The len(argv) == 10 assertion at line 130 would also fail without the change. `pytest -k c5_opencode_dir` selects this test.

- met: The documentation the change affects is updated (C25).

  docs/architecture/modules/opencode.md: the command line now includes `--dir <working tree>`, and a new bullet explains that PWD is set to the same absolute path and why. No other C4/README text describes the opencode command line (grep for 'opencode run' outside work/ and ADRs finds only this module doc).

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  The ticket's 'Decided spec' fixes both choices (--dir with the absolute session.cwd, PWD set to the same path; Claude Code runtime and checks unchanged), so no open choice remains. An amendment note in ADR 0029 would be nice to have (minor finding).

## Proposed learnings (not decided)

- opencode resolves its project directory from the PWD environment variable, not the process cwd; any adapter that copies Ariane's environment must override PWD (or pass an explicit directory flag) for the child's working tree.
- When a ticket adds arguments to a runtime command line, assert on the argv the fake binary actually receives (end-to-end), not only on the command() builder.
