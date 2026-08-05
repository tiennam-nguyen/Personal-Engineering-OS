# Repository Map

## L0 — purpose

PEOS preserves durable intellectual work independently of providers and the SQLite projection.

## L1 — modules

`domain` contains pure values, validation, and typed errors. `ports` holds canonical repository
and derived-index contracts. `application` orchestrates create, lookup, search, verification, and
rebuild. Filesystem and SQLite adapters implement the ports. `bootstrap` wires adapters; the CLI
only parses arguments and renders JSON.

## L2 — Milestone 1 flows

Create: `ArtifactService.create_concept` validates →
`FilesystemArtifactRepository.save` atomically writes and rereads canonical bytes → SQLite upsert.
On upsert failure, canonical data remains and `.peos/INDEX_DIRTY` is written.

Lookup: SQLite yields path/hash → filesystem rereads and independently verifies canonical bytes.
Canonical files win on any divergence.

Rebuild: canonical scan/verification → side SQLite database → swap after closed connections.

## Ownership and limitations

Canonical state is `artifacts/knowledge/*.md`; `.peos/index.sqlite3` is derived state. One mutator
per workspace is enforced by `.peos/locks/workspace.lock`. `os.replace` provides same-filesystem atomic visibility and file `fsync`
is best-effort durability; power-loss guarantees are not claimed. SQLite LIKE search is offline but
not a 50,000-artifact performance claim.
## Milestone 2 run topology

- `domain/runs/model.py` owns IDs, states and canonical JSON;
  `domain/runs/events.py:verify_events` validates and replays the authoritative event chain.
- `ports/run_repository.py:RunRepository` isolates storage;
  `ports/fault_injector.py:FaultInjector` is a test-only crash seam.
- `adapters/filesystem/run_repository.py:FilesystemRunRepository` owns immutable run files and the
  append-only, fsynced journal. `workspace_lock.py:WorkspaceLock` serializes full mutating commands.
- `application/runs.py:RunService` freezes input, resumes from durable frontiers, commits canonical
  data before SQLite projection, reconciles identical state, and fails closed on conflicts.
- `workflows/sample.py:prepare` and `verify_prepared` define the only deterministic workflow.

Start flows through frozen input -> committed step-1 evidence -> staged step-2 evidence -> canonical
artifact -> SQLite projection -> outputs -> success. Cancellation preserves durable evidence and
artifacts. There is no run index, arbitrary workflow loading, live-signal cancellation, or model integration.
