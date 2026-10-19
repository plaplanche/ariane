# 0055. The guard tolerates a fast-forward of the base's tracking ref, witnessed by the remote

- Status: accepted
- Date: 2026-10-19
- Capabilities: C11, C9

## Context
The owner runs tickets back to back: the next one starts as soon as one ends, while another may
still run, and finished pull requests are merged in between. Each `ariane start` fetches the base
branch (`git fetch origin +refs/heads/<base>:refs/remotes/origin/<base>`), and the guard's
snapshot holds `refs/remotes/origin/<base>` (ADR 0017, "The base's tracking ref is guarded"), so
that an agent cannot point it at a commit carrying its own reviewer instructions. A merge after a
running ticket started, then the next start's fetch, moved that ref and stopped the running
ticket. ADR 0017 listed this as not covered.

## Decision
- **A fast-forward to the remote's base is tolerated.** When, after the other runs' own changes
  are set aside (`runs.foreign_changes`), the only difference between two snapshots is
  `refs/remotes/<remote>/<base>` moving from `old` to `new`, where `new` descends from `old` and
  `new` is the commit the remote's base branch points to now (one `git ls-remote` of the URL),
  the guard does not stop (`runs.tracking_fast_forward`, called by `flow._TicketRun._unchanged`).
- **The guard takes the new commit.** The tolerated commit replaces `old` in the run's guard
  snapshot, so a later move is measured from it: when the remote advances again and nobody
  fetches, the ref still equals the guard; when someone fetches again, the same rule applies.
- **Any other move still stops**, with the same reason as before: backwards, sideways, to a
  descendant that is not the remote's base (a local commit, or one the remote no longer points
  to), a deletion, or a move together with any other change.
- **The remote is the witness.** An agent writes the local ref but not the remote's base branch:
  the remote check (`git.remote_changes`) sees any push to it that is not a fast-forward, and an
  agent has no credentials. A commit the remote's base points to is what any fetch would bring,
  so it is not the agent's to choose. The check applies whether or not another run is registered.
- **Git is read only once the rest is unchanged.** `is_ancestor` and `ls-remote` run only when the
  tracking ref is the only change left, so no changed configuration or hook drives them.
- **The ticket keeps its start base.** The review range and the delivered commits are computed
  from the ticket's start commit, and the reviewer's base instructions were read once at the start
  (ADR 0028): neither follows the moved ref.
- **Shadow runs and `ariane verify` are unchanged.** A shadow clone has no remote to witness a
  move (`ShadowRun._remote_base` is empty, so any move stops), and `ariane verify` is a single
  hand step that does not run alongside other tickets.

## Consequences
Tickets run back to back while pull requests are merged. A move to the remote's base costs one
`ls-remote` more in that verification. A merged base is not brought into the running ticket
(#145, #146).

## Alternatives considered
- Tolerating any fast-forward of the ref: an agent could point it at a local descendant carrying
  its own instructions.
- Tolerating a move only while another run is registered: the fetch may come from a run that
  ended between two reads of the registry, and the remote is a stronger witness than the
  agent-writable registry.
- Fetching into a ref of the run's own instead of the shared tracking ref: every other git user of
  the repository expects `origin/<base>` to be current.
