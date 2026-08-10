# Recovery

Create `peos --workspace PATH backup create --output BACKUP`, then independently run
`peos backup verify BACKUP`. Restore only to an absent target with
`peos backup restore BACKUP --to TARGET`; overwrite is unsupported. Run doctor after restore.

Canonical migrations require a re-verified backup with the exact workspace ID and generation in the
plan. The derived legacy-index rebuild is the sole backup-free migration. GC also requires explicit
confirmation and a matching verified backup, and only moves candidates to quarantine.

SQLite is disposable: confirm the exact workspace, remove only `.peos/index.sqlite3`, run
`peos --workspace PATH index rebuild`, then `doctor`. Never delete artifacts, objects, run journals,
protocols, evals, or migration records to repair an index.
