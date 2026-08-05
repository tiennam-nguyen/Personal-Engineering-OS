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

Canonical state is `artifacts/knowledge/*.md`; `.peos/index.sqlite3` is derived state. One writer
per workspace is assumed. `os.replace` provides same-filesystem atomic visibility and file `fsync`
is best-effort durability; power-loss guarantees are not claimed. SQLite LIKE search is offline but
not a 50,000-artifact performance claim.
