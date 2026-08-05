# PEOS

Personal Engineering OS is a local-first, single-user modular monolith.

Milestones 1–2 implement a local artifact round trip and one deterministic sample workflow.
Canonical Markdown files are the source of truth; SQLite is rebuildable derived state. The only
artifact type is `knowledge.concept`; no model, protocol, provider, or tool integration exists yet.

```powershell
uv run peos --workspace demo init
uv run peos --workspace demo artifact create --title "Concept" --body "Durable idea" --tag peos
uv run peos --workspace demo artifact get art_<id>
uv run peos --workspace demo artifact search "durable"
uv run peos --workspace demo artifact verify art_<id>
Remove-Item demo\.peos\index.sqlite3
uv run peos --workspace demo index rebuild
```

See [MAP.md](MAP.md), [PLAN.md](PLAN.md), [CONTRIBUTING.md](CONTRIBUTING.md), and [adr](adr).
## Milestone 2 sample run

The only workflow is deterministic and sample-only; it has no model integration. Start it with
`peos --workspace PATH run start sample.derive-concept --input ARTIFACT_ID`. To pause after its
pure first step, add `--stop-after-step prepare-derived-concept`; then use `run inspect RUN_ID`,
`run resume RUN_ID`, `run verify RUN_ID`, or `run cancel RUN_ID`. Runs live under `.peos/runs`.
Their JSONL journal is hash chained, and committed steps are not re-executed on resume. The chain
detects accidental corruption but does not defend against a user who controls the workspace.
Cancellation happens between invocations, not through live process signals. Mutation locking is
local-machine only, and run lookup requires an explicit run ID.
