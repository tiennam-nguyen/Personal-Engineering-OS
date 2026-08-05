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

The original workflow is deterministic and sample-only. Start it with
`peos --workspace PATH run start sample.derive-concept --input ARTIFACT_ID`. To pause after its
pure first step, add `--stop-after-step prepare-derived-concept`; then use `run inspect RUN_ID`,
`run resume RUN_ID`, `run verify RUN_ID`, or `run cancel RUN_ID`. Runs live under `.peos/runs`.
Their JSONL journal is hash chained, and committed steps are not re-executed on resume. The chain
detects accidental corruption but does not defend against a user who controls the workspace.
Cancellation happens between invocations, not through live process signals. Mutation locking is
local-machine only, and run lookup requires an explicit run ID.

## Milestone 3 protocol and mock model

Protocols are workspace assets: `protocols/registry.yaml` points to exact versioned Markdown bytes,
such as `protocols/sample.concept-summary/1.0.0.md`, whose SHA-256 is frozen in model runs. Inspect
them read-only with `protocol list` and `protocol verify NAME VERSION`.

Start with `run start sample.mock-summarize-concept --input ARTIFACT_ID`. Equivalent requests use a
workspace-local derived cache; `--no-cache` bypasses reads and writes. Use
`--stop-after-step mock-summarize-concept`, `run inspect`, `run resume`, and `run verify`. Trusted
instructions, verified context data, and output schema remain separate channels; context text never
becomes an instruction.

The only adapter is a deterministic offline mock. `mock_whitespace_v1` is not provider-native token
usage. PEOS makes no model-quality claim, uses no provider credentials/network, and has no fallback.
