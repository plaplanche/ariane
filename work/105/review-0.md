# Review 0

- Reviewed commit: `8e77cce244935db27c57e14bc6e94482907687ed`
- Reviewer model: claude-opus-5-5
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/cli.py:155`) `ariane verify --issue` skips the issue gate

  The issue requires the gate for both `ariane start` and `ariane verify --issue`. `_verify` still builds `GitHubTracker(repository=..., token=..., api_url=...)` without `ready_label`. Because `ready_label` defaults to None and `read_issue` only runs `_check_trusted` when it is not None, `verify --issue N` reads the title and body of any issue, unlabelled or edited by an outsider, and hands them to the reviewer. The ADR ("so for `ariane start` and `ariane verify --issue`") and the README claim protection that does not exist on this path. The fix is to pass `ready_label=cfg.tracker.ready_label` here.

- **blocking** (`src/ariane/github.py:41`) The gate is off by default (fails open)

  `GitHubTracker(..., ready_label=None)` disables the security check without any error. Each caller has to remember to opt in, and the verify path shows that one already forgot. Make `ready_label` a required keyword, or default it to the configured label, so the check cannot be left out without anyone noticing.

- **blocking** (`tests/test_c21_issue_gate.py:200`) No test covers `verify --issue` or the CLI wiring

  All gate tests construct `GitHubTracker` directly with `ready_label`, and `flow.start` gets a tracker built by the test. Nothing checks that `cli._start` or `cli._verify` pass the configured label, or that `ariane verify --issue` exits 2 on a refused issue. That gap is why the missing wiring at cli.py:155 got through with all checks green. Add a test for verify with a refused issue (exit 2, nothing checked out or reviewed), plus one for CLI-level wiring.

- **minor** (`docs/architecture/modules/verify.md:1`) Module docs for touched modules not updated

  verify.py (`Refused.exit_code`, which now passes through the tracker's exit code and next action), flow.py (the start exit code now comes from `TrackerError.exit_code`, and refusal gives 2) and cli.py were changed, but docs/architecture/modules/verify.md, flow.md and cli.md were not touched (Ariane flagged them). config_schema.md may need a mention of the new key too. CLAUDE.md rule 11 asks for the `modules/<module>.md` of every module touched.

- **minor** (`src/ariane/github.py:143`) Permission lookup errors surface as exit 1, not as a refusal

  For a non-collaborator or deleted user, `/collaborators/{user}/permission` can return 404. `_request` then raises a plain `TrackerError` (exit 1, next action "check the number") instead of `IssueRefused` with the fix message. The gate still fails closed, but the message is misleading. A 404 here should mean no permission.

- **minor** (`src/ariane/github.py:120`) Only the last body edit is visible

  The ADR records this limitation. A reader's malicious edit followed by a trivial writer edit passes, and the writer may not have reviewed the reader's text. GraphQL `userContentEdits` would show the full edit history if stronger assurance is wanted later.

- **blocking** Definition of done not met: The change is covered by tests that fail without it.

  tests/test_c21_issue_gate.py has 13 `test_c21_issue_gate_*` tests that exercise GitHubTracker, config and flow.start and would fail without the change. They do not cover `ariane verify --issue` or the CLI passing `ready_label`, and that path is broken (cli.py:155).

- **blocking** Definition of done not met: The documentation the change affects is updated (C25).

  Updated: the ADR, github.md, config.md, tracker.md, the regenerated schema, the example toml, ariane.toml and README. Not updated: modules/verify.md, flow.md and cli.md, although those modules changed. The README and ADR also state that `verify --issue` is gated, which the code does not do.

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

- **not met**: The change is covered by tests that fail without it.

  tests/test_c21_issue_gate.py has 13 `test_c21_issue_gate_*` tests that exercise GitHubTracker, config and flow.start and would fail without the change. They do not cover `ariane verify --issue` or the CLI passing `ready_label`, and that path is broken (cli.py:155).

- **not met**: The documentation the change affects is updated (C25).

  Updated: the ADR, github.md, config.md, tracker.md, the regenerated schema, the example toml, ariane.toml and README. Not updated: modules/verify.md, flow.md and cli.md, although those modules changed. The README and ADR also state that `verify --issue` is gated, which the code does not do.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  docs/adr/0032-issue-gate.md (next free number after 0031) records the rule and the alternatives the issue asked for (author allow list, no check). It also records the open choices: an edit in the same second as the label counts as after it, a deleted actor has no permission, the GraphQL endpoint on GitHub Enterprise Server, and that only the last edit is visible.

## Proposed learnings (not decided)

- A security check enabled by an optional constructor argument fails open: make it required so a call site that forgets it is a type error.
- When an issue says a rule applies to several commands, check every place the shared object is constructed (grep the constructor), not only the shared method.
- Gate tests that build the guarded object directly do not prove the CLI wires it; add at least one test per entry point.
