# 0054. Dependency cache for the replay: folders stored by key-file content and copied

- Status: accepted
- Date: 2026-10-19
- Capabilities: C9

## Context
C9 replays every check in a clean tree, and since ADR 0041 each check has its own fresh tree,
set up by `project.setup` (or the check's own `setup`). For a project with Node dependencies that
means `npm ci` in every tree of every round: on a ten-ticket benchmark project the replay trees
held several gigabytes of identical `node_modules`, and the installs cost minutes per round. The
clean tree is the point of C9 (nothing the agent left can make a check pass), but the
dependencies installed from the same lock file are the same every time. Issue #209 decided the
behaviour; this ADR records it and the choices it left open.

## Decision
- **Declared caches.** `[[project.cache]]` tables, each with `path` (a folder relative to the
  tree, ignored by git), `key` (files whose content identifies the folder) and `setup` (the
  command that builds that folder alone), and `keep` (default 5). Paths stay inside the tree (no
  `..`, not absolute, not under `.git`) and two caches never overlap, so each folder has one
  owner. Without any table nothing changes: no store, no copy, no pruning, no journal entry.
- **The key.** The SHA-256 of a version tag, of the `setup` argument list, and of each key file's
  name and content in the replayed tree, in the declared order; a missing key file counts as
  missing, not as empty. The names are hashed with the contents so two files cannot trade
  content unseen. Any change to a key file or to the setup gives a new key, so the folder is
  built again; an old entry is never updated in place.
- **The store.** `<repo>.ariane/cache/<key>/`, next to `worktrees/`, holding `data/` (the folder)
  and `entry.json` (path, key, setup, id). On a miss, the cache's `setup` runs in the fresh tree
  through the same guarded setup as `project.setup` (allow-list environment, guard snapshot
  compared, survivors killed, untracked files refused, ADR 0024, 0031), then the folder is copied
  into `<key>.partial-<random>/data`, made read-only, `entry.json` written, and the temporary
  entry renamed to `<key>`. Before anything is stored, the replay tree must still be at its
  commit, have no change to a tracked file or the index, and hold no file git does not ignore: the checks' own verification comes after the
  store, so a setup that moved the head would otherwise leave an entry built from another
  commit. On a hit, `data/` is copied into the fresh tree instead of running
  that setup, and `entry.json` is touched (its time is the entry's last use). `project.setup` (or
  the check's own `setup`) then runs as before, for whatever the caches do not cover. A hit skips
  the cache's setup, not its checks: right after each copy, before the next cache's setup, the
  tree must hold no file git does not ignore (a commit can drop the ignore rule and keep the key
  files), so no later setup, agent or check runs first and can hide it.
- **Copies, not links.** Each file is copied as a copy-on-write clone where the file system
  supports it (`FICLONE` on Linux: Btrfs, XFS; `clonefile` on macOS: APFS), else as a plain
  copy; after a first refusal the rest of the folder is copied plainly. Never hard links nor a
  link to the store: a tool writing into the folder (a cache file, a rebuilt native module) would
  then change the store, and the next tree would not be clean. Symbolic links inside the folder
  stay links, the copies are writable, modes are kept.
- **Only complete entries.** An entry is used only when its `entry.json` reads, names the same
  path and key, and `data/` exists. A temporary entry (no completion rename) is never read; an
  entry without a readable `entry.json` is rebuilt and replaced, and so is an entry whose folder
  cannot be copied (each entry has a random `id`; the rebuild replaces the entry with the `id` it
  failed to copy, never a newer one). A hit is copied into a hidden
  folder next to the cache's path and renamed to it once complete; a copy that fails half-way (a
  file that cannot be read) removes that folder and the parent folders it made, and the cache is
  built instead: the tree never holds part of an entry.
- **The destination is never followed.** The paths in `[[project.cache]]` are checked when read,
  but the commit decides what is on disk: a folder on the way that is a symbolic link would send
  the copy outside the tree. Before a restore, every existing folder on the way must be a real
  folder and the path itself must not exist; otherwise the cache's setup runs as without a cache
  and nothing is stored. A folder the commit already has at the path is not merged with an
  entry either (a merge cannot be undone atomically). The check is repeated after the setup,
  before storing.
- **One lock for the store.** `<store>/.lock`, an operating-system lock freed when its process
  dies, is held to restore an entry, to publish or replace one, and to prune. Publishing checks,
  under the lock, whether a complete entry is already there: if so it is kept and the copy
  dropped (two trees storing the same key: the first one wins), else an unreadable entry is
  removed and the temporary entry renamed. Without the lock, a tree that had seen an unreadable
  entry could remove the complete entry another tree had just published, and pruning could
  remove an entry a tree was copying. The cost: trees restoring at the same time copy one after
  the other; building and copying a build to its temporary entry run outside the lock.
- **Only replay trees fill the store.** Ariane's replay trees are created from the commit and
  their caches are built before any check runs, so what is stored is what that commit's key
  files and setup produce. The ticket's own tree, where the agent works, gets the caches too
  (a hit is copied, a miss built), but never stores them: the agent could change the folder
  there before Ariane copied it. `ariane verify`'s replay trees are replay trees and fill it.
- **Journal.** `ticket.checks.cache` lists, per check, each cache `hit` or `built` (stored, or
  why not), with the start of its key; `ticket.setup` says the same for the ticket's tree and
  names the entries pruned. `verify`'s `review.md` has a `Dependency caches` section.
- **Limits.** At the start of a ticket (`ariane start`) with at least one `[[project.cache]]`, the entries of each path beyond its
  `keep` most recently used ones are removed (5 for a path no longer declared), with the
  unreadable entries and the temporary entries older than a day (a killed run's). `verify` does
  not prune.

## Measurement
A Node project with 6 development dependencies (TypeScript, ESLint, Vitest, Prettier, webpack,
`@types/node`: 100 MB, 5,841 files in `node_modules`), its lock file in git, and four checks: a
replay builds four fresh trees. Each tree's dependency setup was timed, with npm's own download
cache warm, on the Linux machine of this ticket's session (ext4, which cannot clone files, so the
copies are plain copies):

| Replay | Tree 1 | Tree 2 | Tree 3 | Tree 4 | Total |
| --- | --- | --- | --- | --- | --- |
| Before: `npm ci` in each tree | 3.2 s | 3.2 s | 3.5 s | 3.2 s | 13.1 s |
| After, empty store | 5.6 s (built, stored) | 2.6 s (hit) | 2.8 s (hit) | 2.8 s (hit) | 13.8 s |
| After, next round | 2.9 s (hit) | 2.7 s (hit) | 3.2 s (hit) | 2.8 s (hit) | 11.6 s |

With npm's download cache empty, `npm ci` took 4.4 s per tree. On this machine the gain is small:
creating 5,841 files costs about as much as npm's extraction from its warm cache (`cp -r` of
the same folder alone took 2.2 s), and the store holds one more copy per key (111 MB). Most of the
gain comes where `npm ci` itself costs: a cold or remote package registry, install scripts that
compile, slow file systems for npm's many small writes, and file systems that clone (Btrfs, XFS,
APFS), where a copy writes no data. Those were not available to measure here; the benchmark
project's minutes per round are the case the decision targets.

## Consequences
- A replay copies a stored folder instead of reinstalling it; the trees stay fresh, and a write
  into a tree's copy never reaches the store or another tree.
- The key decides what a hit means: every file the cache's setup reads should be in `key`. A
  file it reads that is not there (for Node, `package.json`'s install scripts) can change the
  folder without changing the key; the entry built first under that key is then reused.
  Content addressing still keeps it per key: another commit hits that entry only with the same key
  files and setup.
- A folder must be relocatable to be cached. A Python virtual environment is not quite: its
  scripts name the tree that built it, and an editable install of the project points into that
  tree. The documented uv example caches the dependencies only (`uv sync --frozen
  --no-install-project`), lets `project.setup` install the project, and runs tools with
  `python -m`.
- The store grows by one folder per key, bounded by `keep` per path; it lives outside the
  repository, next to the working trees, and is never shared between machines.

## Alternatives considered
- **Hard links or a symbolic link to the store.** Fastest and smallest, but a write into the
  tree's folder would change the store (and every later tree): not a clean tree any more.
- **Keeping the trees between rounds.** Saves the copy too, but what a check or the agent left in
  a tree would reach the next check: the opposite of C9.
- **Only npm's or uv's own download cache.** They already exist and are kept; the extraction and
  the install scripts still run in every tree.
- **A key from file times or the setup alone.** Cheap, but a changed lock file would reuse an old
  folder; only the content says the dependencies are the same.
- **Filling the store from the agent's tree too.** One build fewer per ticket, but the agent
  works in that tree and could change the folder before it is stored, for every later ticket
  with the same key.
- **Pruning after every replay, or by size.** Pruning at the start of a ticket is enough to
  bound the store and never removes an entry a running replay of the same ticket just wrote;
  a size limit would need a measure of every entry for little gain.
