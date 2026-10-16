# Review 2

- Reviewed commit: `13d42a30f78517301df153f9ac42da7eec7e425d`
- Reviewer model: claude-opus-5-5
- Verdict: **go**

## Findings

- **minor** (`docs/adr/0039-generated-architecture-blocks.md:24`) ADR says a spaced arrow fails the check, but the code and test check it like any other arrow

  The amended ADR says an arrow written with spaces around it (`A ->> B:`) "fails the check". In fact the ARROW regex in tests/test_docs_sequences.py:11 allows `\s*` around the operator. test_c25_sequences_actor_target_and_unknown_arrow shows that `A ->> C: spaced` is checked against the import graph: it is only reported because `a` does not import `c`. A spaced arrow between modules that do import each other passes. The intent (no call escapes the import check) still holds, but the ADR sentence does not match what the code does and should be reworded.

- **minor** (`tests/test_docs_sequences.py:11`) Arrow kinds the regex does not know are silently skipped

  Lines that do not match ARROW are ignored, not reported. The ADR says any other arrow kind fails, but Mermaid's bidirectional arrows (`<<->>`, `<<-->>`) do not match the regex at all, so a module call drawn with one of them escapes the check silently. The same goes for a sequence block that starts with a comment or a directive before `sequenceDiagram`, because the block regex requires `sequenceDiagram` right after the fence. Today's docs use neither, so this is a robustness gap, not a current miss.

- **minor** (`tests/test_docs_sequences.py:63`) The repository-wide test would also pass on the old diagrams

  The arrows in the old `start` and `verify` sequences (flow->checks, flow->runtime, verify->runtime) are real imports. So test_c25_sequences_repository_passes would pass without the documentation update. The `len(seen) > 50` floor is a weak guard. The tmp_path tests are new and do fail without the checker, so the checker itself is covered.

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

  tests/test_docs_sequences.py is new and adds three test_c25_sequences_* tests. Two tmp_path tests check that a missing import is reported with its file and arrow, and that return arrows, self-calls and arrows to an actor are ignored; they also check that unknown arrow kinds and undeclared participants are rejected. The third test runs the check on the repository's own sequences. None of these tests exist without the change. The repository test alone would also pass on the old docs (minor finding).

- met: The documentation the change affects is updated (C25).

  Updated: 1-context.md (shadow, report, judge, status; the --shadow note), 2-containers.md (shadow store, ticket folder files, verify metrics.json, report/judge arrows), 3-components.md (5 sequenceDiagram blocks: start, start --shadow, verify, report, judge; the start sequence now goes through replay/review_session/metrics), README.md (says the sequences are hand-written and checked by tests/test_docs_sequences.py), and the ADR 0039 amendment. I checked the arrows against the imports of shadow.py, report.py, replay.py, review_session.py, verify.py, flow.py and measures.py. One ADR sentence about spaced arrows is inaccurate (minor finding).

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  The ADR 0039 amendment records the open choices: other arrow kinds fail, undeclared participants are an error, and type-only edges count. The spaced-arrow wording does not match the code (minor).

## Proposed learnings (not decided)

- When an ADR describes how a checker behaves, compare each sentence with the test's assertions. Here the ADR said spaced arrows fail, while the test shows they are checked.
- A doc-vs-code checker should report lines it cannot parse inside the checked block, instead of skipping them. Otherwise new syntax (e.g. Mermaid's bidirectional arrows) escapes the check silently.
