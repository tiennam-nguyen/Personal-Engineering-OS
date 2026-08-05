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

## Milestone 4 plain-text research

Place one to four local `.txt` sources under `inbox/`, install and verify the versioned
`research.claim-extraction@1.0.0` workspace protocol, then run:

```powershell
peos --workspace PATH research compile --question "Is it effective?" `
  --source inbox/a.txt --source inbox/b.txt
```

Use `--stop-after-step ingest-research-inputs`, then `run inspect`, `run resume`, `run cancel`, and
`run verify`; `--no-cache` bypasses extraction cache reads/writes. Raw bytes are preserved under
`.peos/objects/sha256/`. Outputs are `research.question`, `research.source`, `research.claim`,
`research.contradiction`, and `research.synthesis` artifacts.

Extraction uses exact line/byte locators. A line containing invalid UTF-8 is marked unreadable and
never replacement-decoded or sent to the mock. The deterministic grammar ignores blanks, headings,
and question lines; standalone `not` supplies negative polarity. Contradictions require the same
normalized key with opposing polarity. Synthesis text is recomputed from committed claims only.
URLs, PDF, web crawling, OCR, semantic search, embeddings and real providers are unsupported.
