# 0050. A machine-wide run slot, given to the project as `ARIANE_SLOT`

- Status: accepted
- Date: 2026-10-18
- Capabilities: C11, C22

## Context
A project's checks and agents often start local services on fixed ports. In the benchmark on a
reference project, two Ariane runs on one machine (two attempts on two repositories) started the
project's local stack on the same port, and one replay failed for that reason only. The
non-functional requirements say that several projects on one machine never share state; C11
that two tickets never share a working tree; C22 that Ariane tells each session its role in an
environment variable, so the project's instructions can adapt. Ariane does not know a project's
ports, and one Ariane instance per machine (C13) is frozen, so runs of several repositories do
run at the same time. Issue #142 decided the behaviour; this ADR records it.

## Decision
- **Slot.** At its start, before the setup and before any branch, tree or clone, `ariane start`
  (after the ticket lock), `ariane start --shadow` and `ariane verify` take the lowest slot `k`
  from 0 to 15 whose file `~/.ariane/slots/<k>.lock` they can lock, and hold it to their end
  (`slots.held`). The lock is an operating-system file lock (`fcntl.flock` on POSIX,
  `msvcrt.locking` on Windows), the same helper as the ticket lock (`slots.try_lock`): closing
  the file, or the death of the process, releases it, so no slot outlives its run. The folder is
  created when missing; the files stay and hold nothing.
- **Limit.** 16 slots. All held: the run refuses before any branch, "16 Ariane runs already hold
  a slot on this machine. Next: wait for one to end." It never waits.
- **Place.** `~/.ariane/slots/`, in the user's home: shared by every repository of the user on
  the machine, outside every repository and its `<repo>.ariane/` folder.
- **Given to the project.** `ARIANE_SLOT=<k>` is set in the environment of the setup, every
  check, every agent session and the commit hooks (`context.untrusted_environment(slot=…)`),
  after Ariane's own `ARIANE_*` variables are withheld: an `ARIANE_SLOT` in Ariane's own
  environment never passes.
- **Records.** The journal's `ticket.started` entry names the slot; `ariane verify`'s committed
  `review.md` ends with a `Run` section naming it.

## Consequences
- A project derives its ports, or anything else two runs must not share, from `ARIANE_SLOT`
  (for example a base port plus the slot); the README shows it in PowerShell and bash.
- Two runs on one machine never see the same slot at the same time, whatever their repositories.
- A 17th concurrent run refuses instead of waiting. Runs started by different users of one
  machine have different homes, so they do not share slots.
- One slot per run: several slots per run (for parallel checks) are left to a later decision.

## Alternatives considered
- A per-run lock on resources declared in `ariane.toml` (ports, services): it would serialise
  the runs that share a resource, and would not help an agent that starts the stack itself.
- Ariane choosing or rewriting the project's ports: Ariane does not know them, and it is out of
  scope of #142.
- A slot folder per repository (`<repo>.ariane/slots/`): two repositories on one machine, the
  benchmark's case, would get the same slot.
- No limit (the next free number, however high): a project's derived ports would have no known
  range; 16 is above any number of runs one machine runs at once today.
