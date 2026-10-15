# Review 0

- Reviewed commit: `0b060b5d5cbd1447706bfab63baa90ce559f31ad`
- Reviewer model: claude-opus-5-5
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`README.md:151`) The shadow path leaves out the required `ariane` label, so the user's first `ariane start --shadow` exits 2

  `shadow.start` calls `tracker.read_issue`. In `GitHubTracker.read_issue` (src/ariane/github.py:54), `_check_trusted` refuses with IssueRefused any issue that lacks the `tracker.ready_label` label (default `ariane`), whose label was added by someone without write access, or that changed after the label was added (ADR 0032). Shadow mode goes through the same gate. The new section's step 3 ('Per ticket, fetch, run `ariane start --shadow <n>` ...') never says to add the label, and does not link to the paragraph that does (README:74-78). The ticket asks for a complete path that a second user can follow on their own project. Followed as written, every ticket is refused before anything runs. Add a step such as: put the label `ariane` on each ticket (by a person with write access), and add it again after any edit or comment.

- **blocking** (`README.md:161`) `cp docs/ariane.example.toml ariane.toml` fails in the user's repository

  The section is for a second user who installed Ariane with `uv tool install git+...` and works in their own repository. That repository has no `docs/ariane.example.toml`: the file exists only in Ariane's repository, and the package does not ship it (no package-data for it in pyproject). The bash `cp` and the PowerShell `Copy-Item` (line 174) both fail with 'no such file'. Give a command that works from the user's repository, for example download the raw file from the Ariane repository with curl / Invoke-WebRequest, or say plainly to copy it from the linked file on GitHub.

- **minor** (`README.md:164`) The copy-paste blocks run both `accept` and `reject` on the same ticket

  Both code blocks run `ariane judge 12 accept --minutes 20` and then `ariane judge 12 reject --minutes 20`. Pasted as is, the second command overwrites the first: the earlier judgement moves to `judgements_before`, so the ticket ends up rejected. The prose note '(Use one of accept or reject per ticket.)' comes after the blocks. Keep one line, for example `ariane judge 12 accept --minutes 20   # or reject`, the way the earlier section does.

- **minor** (`README.md:187`) Says `shadow pass` covers all five criteria, but the code checks only three

  The README says `ariane report` prints `shadow pass: yes|no` 'for these'. `measures.shadow_lines` (src/ariane/measures.py:121-126) checks only three things over the last 10 tickets: 10 shadow tickets exist, no push, pull-request or guard-violation attempts, and at least 8 accepted. It does not check 'no write to real data' or 'cost and duration recorded'. The earlier README text (line 125) is accurate. Reword it, for example: 'prints shadow pass: yes|no over the last 10 (no attempt, no violation, at least 8 accepted)'.

- **minor** (`tests/test_docs_readme_shadow.py:22`) The tests only look for the words, so they can't catch errors like the two blocking findings

  The tests check that the heading exists, that 'never pushes' and '10 tickets' appear, and that the three command names appear in bash and powershell blocks. That meets the ticket's acceptance criterion, but nothing checks that the path can actually be followed, so both blocking findings above passed. A cheap extra check would be that the section mentions the ready label.

- **blocking** Definition of done not met: The documentation the change affects is updated (C25).

  The README gains the shadow section and an updated status line, and no other document contradicts it (grep finds no 'slice 4 is next' text in docs/). But the new section is wrong in two places: it leaves out the required `ariane` label (src/ariane/github.py:54-78), and its config copy command points at a file that does not exist in the user's repository. So the documentation does not yet describe how the code actually behaves.

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

  tests/test_docs_readme_shadow.py asserts that the heading '## Measure Ariane on your project (shadow mode)' exists, along with its phrases and its bash/powershell commands. On the base commit, `section()` fails its `assert HEADING in text`. `pytest -k c19_readme_shadow` selects 2 tests, and Ariane's replayed test check passed.

- **not met**: The documentation the change affects is updated (C25).

  The README gains the shadow section and an updated status line, and no other document contradicts it (grep finds no 'slice 4 is next' text in docs/). But the new section is wrong in two places: it leaves out the required `ariane` label (src/ariane/github.py:54-78), and its config copy command points at a file that does not exist in the user's repository. So the documentation does not yet describe how the code actually behaves.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  The change is documentation only and follows the ticket's decided spec. It makes no design choice the spec leaves open, so no ADR is needed.

## Proposed learnings (not decided)

- Check user-facing walkthroughs against every gate the command enforces (here, the ready-label check in GitHubTracker.read_issue), not just against the command names.
- Commands meant for a second user's repository must not use paths that exist only in Ariane's own repository (docs/…).
- Copy-paste blocks should not chain alternatives (accept, then reject) that overwrite each other's state.
