# Review 1

- Reviewed commit: `fcaacd55cc4cd660c35fd443d86cfd31706e8b1b`
- Reviewer model: claude-opus-5-5
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`tests/test_docs_sequences.py:12`) Rejecting other arrow types is an undocumented design choice

  The spec only says that solid `A->>B` arrows between modules are checked and that return arrows and self-calls are not. It says nothing about async (`-)`, `--)`), cross (`-x`, `--x`) or open (`->`) arrows. The implementation picks one option for those: OTHER_ARROW reports them as failures ("is an unchecked arrow") in every sequence, even when an actor or a non-module participant is involved. `test_c25_sequences_actor_target_and_unknown_arrow` asserts this behaviour. The amendment to ADR 0039 (docs/adr/0039-generated-architecture-blocks.md) doesn't mention it, so the decision is recorded nowhere, and CLAUDE.md rule 2 requires an ADR for it. Fix: add a sentence to the ADR 0039 amendment saying that any other arrow kind fails the check so that it can't escape the import check.

- **minor** (`docs/architecture/3-components.md:195`) Shadow sequence names a function that does not exist

  `CLI->>H: run_shadow` names a function that isn't in the code. cli calls `shadow.start` (src/ariane/cli.py:203). The label should be `start`. The same sequence also leaves out the fix-round loop that the spec covers with "the same implementer, replay and review steps". ShadowRun inherits `_TicketRun`, so it runs up to two fix rounds.

- **minor** (`docs/architecture/3-components.md:258`) Report sequence overstates what metrics and shadow do

  `P->>M: read work/*/metrics.json` and `P->>H: read the metrics of the shadow clones` both say another module does the reading. In fact report.build reads and validates every JSON file itself (`_read`, `_shadow_paths`). It only takes the `metrics.METRICS` name and `shadow.clone_path` from those modules. The import edges exist, so the test passes, but the messages misstate who does the work.

- **minor** (`tests/test_docs_sequences.py:11`) Arrows the parser doesn't recognise are skipped silently

  ARROW only matches `A->>B:` with no spaces around the arrow. PARTICIPANT only sees declared participants, and the label has to come after `as`. An arrow written `A ->> B:` (valid Mermaid) is never checked, and neither is a participant that is only declared implicitly by an arrow. Also, `test_c25_sequences_repository_passes` doesn't assert that any arrows were found, so a parser that stopped matching would let it pass without checking anything. Only the tmp_path tests would catch that.

- **minor** (`docs/architecture/1-context.md:15`) Level 1 labels leave out the optional and required arguments

  The edge reads `ariane report --since`, but the spec writes `ariane report [--since]`, where the flag is optional. The judge edge leaves out `--minutes N` as a flag and doesn't mention `--note`.

- **blocking** Definition of done not met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  The test treats async, cross and open arrows as failures (OTHER_ARROW in tests/test_docs_sequences.py:12). The spec leaves that choice open, and the ADR 0039 amendment doesn't record it.

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

  tests/test_docs_sequences.py is new and adds 3 `test_c25_sequences_*` tests. The tmp_path tests check that a missing import is reported with its file and arrow, and that return arrows, self-calls and arrows to an actor are skipped. The repository test runs every sequence under docs/architecture/ against the import graph. The old start sequence drew `F->>C` and `F->>R` reviewer calls that the graph no longer supports, so these tests would have caught it. The suite passed in Ariane's replay.

- met: The documentation the change affects is updated (C25).

  These files are updated: 1-context.md (the new commands, the report read from GitHub, the note that shadow and verify never push), 2-containers.md (the shadow store, the full contents of the ticket folder, metrics.json in the verify records, the report and judge edges) and 3-components.md (5 sequenceDiagram blocks). The docs/architecture/README.md table and text now say the sequences are hand-written and checked against the imports, and ADR 0039 is amended. No src/ change, so the module files and generated blocks are untouched, as scoped. A few minor label inaccuracies remain (see findings).

- **not met**: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  The test treats async, cross and open arrows as failures (OTHER_ARROW in tests/test_docs_sequences.py:12). The spec leaves that choice open, and the ADR 0039 amendment doesn't record it.

## Proposed learnings (not decided)

- When a checker test rejects input that the spec doesn't mention, such as other Mermaid arrow kinds, record that strictness in the ADR that describes the check.
- A repository-wide doc consistency test should assert that it actually found something to check (for example, at least one arrow), so it can't pass without checking anything.
- When an arrow passes the import check, the message text can still be wrong: compare it with the function that is really called, such as shadow.start versus a made-up run_shadow.
