# 0011. Learnings: approved before the pull request

- Status: accepted
- Date: 2026-10-07
- Capabilities: C18, C10, C11, C9, C22

## Context
C18: each failure leads to a proposal; agents propose learnings in a fixed format; Ariane
validates them; the human accepts or rejects each one; an accepted rule joins the project's
rules file; relevant learnings are injected into the agents' context within a size limit. The
owner wants each ticket to cost one CI run: nothing is pushed until the learnings are decided.

## Decision
**Order of a ticket**: implement, replay every check locally, review (with its fix rounds,
ADR 0010), collect the learnings proposed by the implementer and the reviewer, then stop and ask
the human to accept or reject each one. Nothing is pushed before that answer. A ticket with no
proposal goes straight to delivery.

**Format**: both sessions answer with structured output (`--json-schema`) that includes
`learnings: [{"kind": "rule" | "fact", "title", "body", "reference"}]`. A rule is a short
instruction for every future session ("never run git in the repository while a ticket runs");
a fact is a point fact useful to some tickets ("the Windows tests check takes about 195 s in
CI"). Ariane validates each one (known kind, title under 100 characters, body under 600, no
duplicate of an existing rule or fact); an invalid proposal is journaled and dropped. Valid ones
get ids `L1`, `L2`... and are listed in `work/<n>/learnings.md`.

**Checkpoint**: the ticket stops with status `learnings awaiting approval` and the next action
`ariane learnings <n> --accept L1,L3 --reject L2="reason"`. Every proposal must be decided; the
command refuses a partial answer and names the missing ids. In autonomous mode (slice 5) this is
a human checkpoint with a notification.

**After the answer** (same command, which then continues the ticket):
- accepted rules are written into the rules file (`[learnings] rules_file`, `CLAUDE.md` for
  Ariane), in its `## Learned rules` section, one entry per rule (title, a few lines, the reason
  and the reference `#<n>`), in one separate commit (the learnings commit); the section's size is checked against
  `[learnings] rules_max_chars` (default 6,000) and the command refuses an answer that would
  exceed it;
- accepted facts go to the learning store, `docs/learnings.md` (`[learnings] facts_file`), one
  section per fact, committed in the same commit as the rules, so the single push carries both
  and they survive any machine, cloud containers included;
- rejected proposals are kept, with the human's reason, in the ticket journal;
- the fast checks (`fast = true` in `[[checks]]`: lint, format, file length for Ariane) are
  replayed, then Ariane pushes once and opens the pull request.

**Review stays current**: before the push, Ariane checks that every commit after the reviewed
commit touches only the rules file, the facts file and `work/<n>/`; otherwise it stops (the
review is stale).

**Resume**: at the checkpoint Ariane persists, outside the repository
(`<repo-parent>/<repo>.ariane/state/<n>.json`), the reviewed commit, the branch head and the git
snapshot of ADR 0007 layer 3. `ariane learnings` refuses to continue unless the branch head and
the git snapshot are unchanged and the ticket branch is still absent from the remote; other
remote refs (a merge on the main branch while the human decides) are read again, not compared,
since no agent runs during the wait.

**Later rules**: a rule the human finds while reviewing a pull request is recorded with
`ariane learnings add-rule "<title>" "<body>"`; it is kept as pending in
`<repo-parent>/<repo>.ariane/pending-rules.md` on that machine and committed into the rules file
on the next ticket's branch, before the implementer starts. The command warns that a pending
rule is lost with the machine (a cloud container, for example).

**Context**: rules reach every session through the rules file, which the agent runtime reads as
project instructions; accepted facts, newest first, up to `[learnings] facts_max_chars`
(default 4,000), go into the implementer's and the reviewer's prompts as a delimited section.

C18 lists rule, test, check and probe as kinds: in slice 2 a proposed test, check or probe is
written as a rule ("add a check that ...") and decided like one; separate kinds come with the
checks they need (slices 4 and 10).

## Consequences
One push and one CI run per ticket; rules and facts are versioned and reviewed with the pull
request that brings them. A pending later rule waits for the next ticket on the same machine.
Pluggable stores come in slice 6.

## Alternatives considered
- Checkboxes in the pull request read by a workflow: a workflow's push does not trigger CI, so
  the pull request would lose its required checks.
- Facts outside the repository (per machine): lost with cloud containers (eng review, D2).
- Checkboxes in the pull request read at the next ticket: the truth would live in GitHub, not
  in the files.
- One file per learning: easier merges, harder to read in one place.
