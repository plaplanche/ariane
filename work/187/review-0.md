# Review 0

- Reviewed commit: `8505bef76bb6159fe6495b7cb579b193f71eb2d3`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`docs/adr/0047-parallel-tests-and-ci-matrix.md:31`) Matrix reduction omits required-status migration

  ADR 0005 states that the repository ruleset requires all six CI job names. Applying the proposed matrix removes macos-latest / Python 3.11 and windows-latest / Python 3.11, leaving those required statuses unreported and blocking merges under the documented ruleset. Add explicit owner handover instructions to update the required statuses alongside the workflow change, retaining the four remaining checks. Verify the actual ruleset during handover.

- **blocking** (`docs/adr/0047-parallel-tests-and-ci-matrix.md:74`) Required CI performance evidence is still missing

  The after measurements are placeholders. The sandbox's 102-second run and Ariane's green replay do not establish that parallel tests pass on macOS and Windows or that this PR's longest CI job finishes under 12 minutes. The owner-deferred workflow edits are explicitly permitted by the ticket, but final acceptance still requires applying them, running this PR's CI, and recording the actual job durations and run reference before merge.

- **minor** (`docs/adr/0047-parallel-tests-and-ci-matrix.md:3`) Previous matrix ADR remains accepted without a supersession notice

  ADR 0005 still specifies six jobs and is marked accepted without mentioning 0047. The ADR README requires marking the replaced portion as superseded. Update 0005's status to identify the matrix decision replaced by 0047.

- **blocking** Definition of done not met: The documentation the change affects is updated (C25).

  README, container documentation and learnings were updated, but ADR 0005 lacks its required supersession notice, the required-status migration is undocumented, and ADR 0047's required CI measurements remain placeholders.

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

  test_parallel_tests_are_the_default_of_uv_run_pytest asserts the new addopts, dependency and lock entry; the base configuration lacks them. Ariane reports the test replay passed. Tests were not rerun during this read-only review.

- **not met**: The documentation the change affects is updated (C25).

  README, container documentation and learnings were updated, but ADR 0005 lacks its required supersession notice, the required-status migration is undocumented, and ADR 0047's required CI measurements remain placeholders.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0047 records default parallel execution, serial override, the decision not to group tests, worker isolation reasoning, matrix reduction, caching and workflow handover YAML.

## Proposed learnings (not decided)

- Proposed: When removing CI matrix jobs, audit required status names and include their migration in the owner handover.
- Proposed: Treat sandbox speedups as preliminary evidence; close performance acceptance only with measurements from the requested CI environments.
