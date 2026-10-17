# Review 0

- Reviewed commit: `450107633201ef549b1617f21ab5f463024e2cb3`
- Reviewer model: claude-opus-5-5
- Verdict: **go**

## Findings

- **minor** (`tests/test_c9_isolated_replay.py:159`) No test validates a config containing checks[].setup against the generated schema

  The acceptance criterion says an `ariane.toml` with `checks[].setup` validates against the generated schema. The tests only cover `config.parse` (accept, and refuse with `checks[0].setup`). `test_docs_reference_config_files_validate` checks the repository's own config files, and in `docs/ariane.example.toml` the `setup` line is commented out, so no file with `checks[].setup` is ever validated against `config.SCHEMA`. The schema entry is `_ARGV`, which is correct by construction, but nothing tests this criterion directly.

- **minor** (`tests/test_c10_reviewer_isolation.py:42`) Replay-keeps-instruction-files assertion now inspects the implementer tree

  The replay tree no longer exists while the reviewer runs, so `replay = tree.with_name("7")` now looks at the implementer's working tree. The test's name still claims the replay keeps the instruction files. No other test shows that a per-check `<n>-replay-<k>` tree keeps CLAUDE.md or AGENTS.md, so that guarantee lost its test.

- **minor** (`docs/architecture/modules/verify.md:20`) verify.md still describes a single replay tree in places

  Line 20 says 'the replay tree and the temporary records folder are removed' and line 23 says 'where the replay tree and the records are', both singular. The workflow diagram (lines 32-33) shows the per-check loop and then a separate `run_checks` step, but the checks now run inside the loop.

- **minor** (`src/ariane/verify.py:198`) `ariane verify` drops the per-tree records

  `replay_each` gets `trees=[]` and the list is thrown away, so verify's records do not list the per-check trees or their setup durations. The ticket ties the `ticket.checks.worktree` journal entry to the ticket flow, so this is not a spec breach, but the two commands' records now differ.

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

  tests/test_c9_isolated_replay.py has 10 `test_c9_isolated_replay_*` tests. The leftover test (a check writes an ignored file, a later check needs it) would exit 0 on the old shared tree, so it fails without the change. The other tests cover: setup counted per check (4 = implementer + 3 checks), `checks[].setup` replacing `project.setup` in its own tree only, no `-replay-` tree left after a green run, a failing check or a Ctrl-C on the second check, `ariane verify` using `verify-hand-iso-1/2`, config accept and refuse with `checks[0].setup`, the leftover tree refused, and the setup stop naming the check.

- met: The documentation the change affects is updated (C25).

  Updated: modules/replay.md, checks.md, verify.md, config.md, config_schema.md and flow.md; the 3-components.md sequences for start and verify; the regenerated docs/reference/ariane.toml.schema.json and docs/logs.md; the README paragraphs on the replay; a commented `setup` line in docs/ariane.example.toml. modules/logs.md (flagged as untouched) needs no change, because only a journal entry's meaning changed, and that lives in the generated catalogue. Minor singular wording remains in verify.md.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  docs/adr/0041-one-clean-tree-per-check.md records the per-check trees, their naming, setup failures, the `checks[].setup` key, the shared `replay_each` function and the records. ADR 0018's status reads 'accepted; clean-tree part superseded by 0041'.

## Proposed learnings (not decided)

- When a change removes a tree or resource that an existing test inspected, check that the rewritten test still asserts the original guarantee, and not just something nearby.
- An acceptance criterion like 'validates against the generated schema' needs a fixture that actually holds the new key; a commented example line is not validated.
