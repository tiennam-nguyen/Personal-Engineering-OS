# Repository Map

## Milestone 5 Project Compiler

- Domain: `src/peos/domain/project/model.py:ProjectRequest`, `result.py:ResultManifest`, and `artifacts.py:validate_project_payload` own strict request/result and exactly-three-artifact contracts.
- Trust boundary: `src/peos/application/project.py:ProjectService._draft` separates trusted intent, optional synthesis context data, and verified repository bytes as untrusted source blocks.
- Evidence: `src/peos/ports/project_estate_reader.py:ProjectEstateReader` and its filesystem adapter bound reads; raw bytes reuse `SourceObjectStore`.
- Flow: `project.compile@1.0.0` snapshots, drafts with `deterministic-project-planner-v1`, then canonically commits map, charter, and packet before SQLite projection.
- Resurrection: `src/peos/domain/project/packet.py:render_packet` reconstructs the packet from canonical map/charter. Resume reuses committed snapshot/plan evidence; cache is derived and `--no-cache` bypasses it.
- Result scope: `src/peos/domain/project/result.py:validate_result_scope` rejects paths outside Allowed before canonical mutation. Accepted bytes are reread/hash-checked and a new map `supersedes` the preserved old map.
- Durable state: canonical artifacts, source objects, immutable evidence, and append-only hash-chained journals are authoritative. SQLite and model cache are derived and rebuildable.
- Boundary: `src/peos/bootstrap.py:open_project_workspace` wires concrete adapters; CLI/application/domain dependency directions remain inward.
- Limits: existing-repository mode, explicit UTF-8 reads, two-level tree names, one walking skeleton, reported result verification, and no repository/Git/Codex/command/network execution.

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
artifacts. There is no run index, arbitrary workflow loading, or live-signal cancellation.

## Milestone 3 protocol and model topology

- `domain/protocols/model.py:ProtocolDefinition` owns protocol identity; the filesystem protocol
  repository verifies strict registry records, canonical paths, UTF-8 bytes, and raw SHA-256.
- `application/context.py:ContextCompiler` selects independently verified canonical artifacts in
  deterministic order. `ContextBlock` retains content only as untrusted data with exact revisions.
- `domain/models/request.py:ModelRequest` keeps instruction, intent, context, source, and schema
  channels separate. `domain/models/audit.py` owns route, cache-key, response-hash, and budget rules.
- Model gateway, cache, and protocol repository are ports. Bootstrap alone wires filesystem adapters
  and `adapters/models/mock.py:DeterministicMockGateway`; application/workflows import no adapters.
- `application/modeling.py:ModelCallService.execute` coordinates protocol, context, request, cache,
  response, budget, and five immutable audit files without committing canonical knowledge.
- `application/runs.py:RunService._execute_model` verifies the prepared result and performs the
  canonical-first artifact commit followed by SQLite projection. Committed model steps are skipped.

Model evidence is below `.peos/runs/<run>/evidence/model-calls/<call>/`; cache below
`.peos/cache/model/` is hashed workspace-local derived state. Miss calls the mock once; hit retains
origin provenance and emits no call events; bypass neither reads nor writes cache. There is no real
provider, network, fallback, retry, semantic retrieval, summary substitution, or cache GC.

## Milestone 4 Research Compiler topology

- `domain/research/model.py` owns source locators and claim values;
  `extraction.py:extract_plain_text` preserves exact line/byte offsets and records invalid UTF-8;
  `claims.py:normalize_claims` performs exact `not`-polarity deduplication and contradiction keys;
  `synthesis.py:synthesis_body` emits only committed claim propositions.
- `domain/artifacts/model.py:Artifact.payload` is optional and omitted from legacy canonical bytes.
  Research payloads and links are strictly validated in `domain/research/artifacts.py` and
  `domain/artifacts/validation.py`.
- `ports/source_object_store.py:SourceObjectStore` points outward to
  `adapters/filesystem/source_object_store.py:FilesystemSourceObjectStore`. Raw source objects under
  `.peos/objects/sha256/` are canonical immutable evidence; SQLite remains derived.
- `application/research.py:ResearchService` freezes inbox inputs, commits question/sources, sends
  readable lines only through untrusted source blocks, normalizes the mock output, then commits
  claims, contradictions, and synthesis in deterministic order. Resume after committed ingestion
  reads objects/evidence, not inbox files.
- `workflows/research.py:WORKFLOW` is the fixed three-step `research.compile-plain-text@1.0.0` flow.
  Bootstrap wires concrete storage and the existing deterministic mock boundary; CLI exposes only
  local `.txt` compilation and generic run lifecycle commands.

Research canonical ownership is split between raw content-addressed objects and canonical Markdown
artifacts. Run/model evidence and cache remain operational/derived. Locators are line-only; invalid
UTF-8 makes the entire line unreadable. There is no URL, PDF, OCR, semantic retrieval, graph
traversal, real provider, or Project Compiler.
