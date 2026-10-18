# 0045. Idle limit of agent sessions

- Status: accepted
- Date: 2026-10-18
- Capabilities: C5

## Context
Each agent session has a total time limit (C5, `agents.<role>.timeout_minutes`), but nothing
noticed a session that had stopped making progress. In the benchmark on a reference project, an
implementer spent about fifteen minutes in a shell loop that could never end, until the shell
tool's own command timeout ended it: the session's budget and time went to waiting. Ariane reads
every session's event stream line by line (`process.stream`), so it can see when no event has
arrived for a long time. C5 asks for a time limit, a stop reason classified by Ariane and a clear
status; it does not say how long a silent session may last.

## Decision
- `process.stream` takes `idle_timeout_s`: when no standard-output line has arrived for that
  long, the whole process tree is killed (as at the total limit) and `Completed.idle` is set.
- `agents.<role>.idle_minutes` (optional, positive, for both roles and every runtime) sets it. A
  value at or above `timeout_minutes` is refused naming the key. Without the key the idle limit is
  10 minutes, or none when `timeout_minutes` is 10 or less (the total limit already applies).
- An idle kill is the stop reason `timeout` (the stop reasons of C5 stay the spec's), with the
  summary "no activity for <m> min (idle limit); last event: <type>", plus "(tool <name>)" when
  the last event was a tool call. The journal's stop entry and the stop line show it; the work is
  kept on the branch as for any timeout.
- Activity is measured on the event stream only, not on file changes in the working tree: the
  stream is what Ariane already reads for every runtime, a session that writes files without
  sending events does not exist (each tool call and result is an event), and watching a tree
  would need a second mechanism per platform.
- Why 10 minutes: Claude Code (checked on version 2.1.302) runs one shell command for 2 minutes by
  default and at most 10 minutes (`600000` ms) unless `BASH_MAX_TIMEOUT_MS` raises that limit.
  While a command runs the session sends no event, so 10 minutes is the shortest limit that
  leaves room for the longest test run the agent may start. The owner may change it per role in
  `ariane.toml`.

## Consequences
A session stuck waiting stops after 10 minutes of silence instead of running to its total limit.
A command that uses the full 10 minutes of the shell tool races the idle limit: a project whose
test run lasts that long, or that raises `BASH_MAX_TIMEOUT_MS`, sets `idle_minutes` higher. A
model that thinks for more than the idle limit without sending an event is stopped too.

## Alternatives considered
- No default (only when configured): the benchmark's loop would still have run to the total limit.
- A shorter default (5 minutes): stops legitimate long test runs.
- Watching file changes in the working tree as activity: a second mechanism per platform, and a
  stuck loop that writes a file would look active.
- A new stop reason `idle`: C5 lists five stop reasons; the summary already says which limit.
