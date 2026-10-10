# Review 1

- Reviewed commit: `a7a317305c6ae8c6f52a1926f24db73ad4747b56`
- Reviewer model: claude-opus-5-5
- Verdict: **go**

## Findings

- **minor** (`docs/architecture/modules/process.md:18`) process.md not updated: opencode missing from collaborations, argument cutting undocumented

  opencode.py now calls process.stream/process.run, but the module's collaboration diagram still lists only checks, claude_code, cli, delivery, flow, git. process.py also gained `_shown`, which cuts each argument to 200 characters in the `process.started` log line. ADR 0029 mentions this, but the module doc does not. Ariane flagged this document as mapped and untouched.

- **minor** (`src/ariane/runtime.py:76`) Login variables are unioned across roles, so the implementer's environment keeps the reviewer's provider key

  RoutedRuntime.login_variables is the union of all runtimes' variables. flow.py:143 builds one environment from it, so an implementer on Claude Code also receives OPENAI_API_KEY (or another provider's key) when the reviewer runs on opencode. ADR 0029 records this union. A per-role environment would follow least privilege more closely.

- **minor** (`src/ariane/cli.py:89`) cli._runtime wiring is not tested

  No test checks that `ariane start` or `ariane verify` builds an OpenCodeRuntime for a reviewer with runtime = "opencode" and passes the model, which is what feeds the login variables. A RoutedRuntime routing test exists, but the CLI selection branch has no test.

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

  tests/test_c5_opencode.py has 16 test_c5_opencode_* tests that drive the adapter through tests/fake_opencode.py, which replays the verbatim fixtures. They cover tokens 1000/3000/240 and cost 0.0075, finished state, the answer validating as no-go through read_answer, the token cap and cost cap giving budget, the error fixture giving error, the inline permission deny, --pure plus OPENCODE_DISABLE_CLAUDE_CODE, and the implementer being refused. tests/test_config.py has 4 test_c22_config_path_* tests for ARIANE_CONFIG relative/absolute paths, validation, missing files and the default ariane.toml. All of these fail without the new modules.

- met: The documentation the change affects is updated (C25).

  Added: modules/opencode.md and modules/config_schema.md. Updated: levels 0 to 3, modules cli/config/flow/runtime/review_session, the architecture README index, the regenerated schema reference ('docs: references' check green), and the README section with PowerShell and bash examples. One small gap: process.md's collaboration diagram does not show opencode and does not mention argument cutting in the log (minor finding).

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  docs/adr/0029-opencode-reviewer.md records the open choices: RoutedRuntime and the union of login variables, the provider key table, steps = 20 as a constant, command-line length limits, the schema appended to the message, the cost and token caps, and resolving the ARIANE_CONFIG path.

## Proposed learnings (not decided)

- When a new adapter calls an existing module, update the callee's module doc collaboration diagram too, not only the caller's.
- Routing runtimes per role while sharing one agent environment spreads each role's login keys to every role; consider per-role environments.
