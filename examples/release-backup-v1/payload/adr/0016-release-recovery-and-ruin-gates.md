# ADR 0016: Release recovery and ruin gates

Status: Accepted

## Context

Milestone 9 introduces backup, restore, migration, and retention operations with workspace-wide blast
radius. Canonical files and immutable evidence, not SQLite, remain authoritative.

## Options considered

1. Archive backup with overwrite restore.
2. SQLite/database-native backup.
3. Strict manifest directory snapshot, absent-target restore, explicit migrations, quarantine GC.

## Decision

Backup v1 is a strict self-contained manifest directory containing all object blobs. Restore never
overwrites and verifies first. SQLite is explicitly schema-versioned derived state. Canonical
migrations require an exact-generation verified backup with no bypass. GC requires the same backup
gate, confirmation, and reference rescan, and v1 only quarantines. Doctor observes but never repairs.

## Consequences

Backups are larger and uncompressed but inspectable and self-contained. Operators must choose new
restore paths and retain backups. Permanent purge, encrypted/remote backup, and automatic canonical
migrations are deferred.

## What would change this decision

Measured backup-size pressure, secure remote backup, multi-device synchronization, or a verified need
for automatic canonical format migrations.
