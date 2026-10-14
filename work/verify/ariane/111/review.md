# Review 0

- Reviewed commit: `edc80e26ef06731ab11323971bed8b350261002a`
- Reviewer model: claude-opus-5-5
- Verdict: **no-go** (the reviewer answered go)

## Findings

- **minor** (`src/ariane/github.py:109`) The 5 s slack lets a change made right after the label through, but the docs say any later change is refused

  `updated > since + _LABEL_SLACK` accepts any edit made up to 5 seconds after the `labeled` event, by anyone, including the reader who wrote the issue. The old rule (ADR 0032, check 3) failed closed: an edit in the very second of the label counted as after it. An attacker who polls their own issue (about 1 request per second fits inside the authenticated rate limit) can swap the body inside that window, and the gate accepts it. The amendment and the README both say "Any later change refuses the issue" and "not changed since", which overstates what the gate guarantees. With REST only, some slack may be unavoidable because body edits leave no event. Even so, the ADR should state the residual window as an accepted risk. Consider a smaller slack (GitHub normally stamps `updated_at` in the same second as the label event), or add a test or measurement that justifies 5 s.

- **minor** (`docs/architecture/modules/flow.md:11`) flow.md still describes the old gate

  It still says an issue is refused when "labelled or edited by someone without write access". After this change, any change after the label is refused, by anyone, writers included. The owner of a user repository is also trusted without a permission call. Rule 11 asks for documentation that describes the behaviour to be updated in the same ticket. The ADR title and Consequences ('three to four requests', 'after any later edit by someone else') are superseded only by the amendment. That is acceptable for an ADR, but the module doc should be current.

- **minor** (`src/ariane/github.py:109`) Ariane's own activity on the issue can make the gate refuse it later

  Only `updated_at` is compared now. Anything that updates the issue after the label makes `ariane verify --issue N` refuse it during a hand takeover after a second no-go, and makes a re-run of `ariane start` refuse it too. That includes another label, a comment, or possibly the cross-reference created when Ariane's own draft pull request says `Closes #N`. The README's 'add it again after any later change' covers this, but neither the ADR amendment nor the README mentions the hand-takeover case. No test covers it either.

- **minor** (`tests/test_c21_issue_gate.py:175`) Some new branches of _can_write are not tested

  No test checks that owner logins are compared without case: the fake owner is 'Olivia' and the labeller is 'olivia', so the comparison happens, but there is no explicit test or comment for it. No test checks that `GET /repos/{repo}` is cached, or what happens when that call itself fails. That failure raises TrackerError (a different exit code from IssueRefused), and this is not documented in the ADR.

- **blocking** Definition of done not met: The documentation the change affects is updated (C25).

  Updated: README, docs/ariane.example.toml, docs/architecture/modules/github.md, and the ADR 0032 amendment. Not updated: docs/architecture/modules/flow.md:11 still describes the old rule ("labelled or edited by someone without write access"). The generated schema description of ready_label is still accurate.

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

  tests/test_c21_issue_gate.py adds: refused when updated_at is after the label; accepted inside the slack; owner of a user repo trusted with permissions returning 403 and no /graphql or /collaborators call; an organisation owner login not trusted; a 403 on the permission check refused with the user's name. The fake no longer serves /graphql and the old code depended on it, so these tests fail on the base commit. test_github.py's `trust` helper was updated accordingly.

- **not met**: The documentation the change affects is updated (C25).

  Updated: README, docs/ariane.example.toml, docs/architecture/modules/github.md, and the ADR 0032 amendment. Not updated: docs/architecture/modules/flow.md:11 still describes the old rule ("labelled or edited by someone without write access"). The generated schema description of ready_label is still accurate.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  The amendment to docs/adr/0032-issue-gate.md records three choices: trusting the owner of a user-owned repository, refusing on a non-404 permission error, and the 5 s updated_at slack that replaces GraphQL and the renamed check. It does not record the residual race window as an accepted risk (see findings).

## Proposed learnings (not decided)

- A gate based on time-window slack is not fail-closed. Document the window as an accepted risk instead of claiming that 'any later change' is refused.
- When a security gate changes, grep every doc for its old wording (here flow.md), not just the module file that was touched.
- An `updated_at` gate also reacts to Ariane's own side effects on the issue, such as cross-references from its pull requests. Think through the re-run and hand-takeover paths.
