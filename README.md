# PEOS

## Cross-Workflow Graph (Milestone 7)

```text
peos --workspace WORKSPACE crossflow bridge --request-file REQUEST.json
peos --workspace WORKSPACE graph ARTIFACT_ID --depth 1
```

Cross-workflow relations live once in canonical artifact metadata. Legacy `{rel,target}` links are
outgoing; a newly created target may host `{source,rel}` so historical sources remain byte-stable.
Reverse navigation returns the same directed edge rather than persisting an inverse relation.
SQLite stores only rebuildable adjacency/backlinks with canonical-host revisions, and every graph
row is checked against its canonical host before use.

The deterministic bridge supports exactly: reported project failure→`learning.exercise`, SUPPORTED
research claim→`project.adr`, and exact learning gap→`research.question`. No model chooses links;
project failures remain reported rather than PEOS-executed evidence. Deleting the derived index and
running `index rebuild` restores graph traversal. There is no arbitrary graph editor, semantic
relation inference, graph database, crossflow model call, or evaluation framework in Milestone 7.

## Learning Compiler (Milestone 6)

Learning Compiler deterministically turns a strict capability goal and diagnostic fixture into a
durable plan, then records evidence for its planned first exercise:

```text
peos --workspace WORKSPACE learn compile --goal-file GOAL.json --diagnostic-file DIAGNOSTIC.json
peos --workspace WORKSPACE learn attempt --goal GOAL_ARTIFACT_ID --attempt-file ATTEMPT.json
peos --workspace WORKSPACE run inspect|resume|cancel|verify RUN_ID
```

Compile may stop after `freeze-learning-inputs` or `analyze-learning-gap`. Inputs are frozen before
analysis, so resume does not reread modified or deleted files. Attempts require the exact goal
revision and planned exercise. Only exact-text and single-choice verification exist.

The only learning artifacts are `learning.goal`, `learning.attempt`, and `learning.mastery`.
Mastery keeps recall, explanation, application, transfer, and retention distinct; same-session
retention remains `NOT_ASSESSED`. `fixed_interval/v1` review dates are recommendations, not proof
of mastery. SQLite remains derived: delete only `.peos/index.sqlite3`, run `index rebuild`, and
canonical learning artifacts remain available. No model, semantic grader, scalar score, mastered
boolean, or cross-workflow graph is part of Milestone 6.

## Project Compiler (Milestone 5)

Project Compiler supports one existing local repository, explicit UTF-8 reads with a named question, optional exact `research.synthesis` context, and one walking-skeleton packet. With workspace-owned `project.plan-compilation@1.0.0` installed:

```text
peos --workspace WORKSPACE project compile --request-file REQUEST.json
peos --workspace WORKSPACE project export-codex PACKET_ARTIFACT_ID
peos --workspace WORKSPACE project accept-result --packet PACKET_ARTIFACT_ID --result-file RESULT.json
peos --workspace WORKSPACE run inspect|resume|cancel|verify RUN_ID
```

Compile accepts `--stop-after-step snapshot-project-inputs`, `--stop-after-step draft-project-charter`, and `--no-cache`. The strict request freezes intent, stakeholder, intolerable failure, constraints, done contract, root, ordered read/path/role/question records, flow, candidate/forbidden scope, exact verification contract, optional synthesis ID, and sensitivity.

PEOS does not modify the target repository, run Codex, run arbitrary commands, or execute packet verification. Repository content is data-only. Result verification is reported, not PEOS `[RAN]` evidence. The deterministic mock is not evidence of architecture quality. Only existing-repository mode, one walking skeleton, and canonical `project.map`, `project.charter`, and `project.codex_packet` exist in Milestone 5.

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

## Milestone 8 evaluation and qualification

Production model routes fail closed until their exact active suite has a valid latest canonical
evaluation report. Suites and goldens are reviewed static files under `evals/`.

```powershell
peos --workspace PATH eval run model.summarization.core `
  --provider mock --model deterministic-concept-summary-v1 --model-revision 1
peos --workspace PATH eval compare RUN_A RUN_B
peos --workspace PATH run inspect RUN_ID
peos --workspace PATH run resume RUN_ID
peos --workspace PATH run cancel RUN_ID
peos --workspace PATH run verify RUN_ID
```

Evaluation calls always bypass cache. Resume reuses only journal-proven validated response audits;
an interrupted call with unknown outcome is not retried. Qualification binds the exact task, route,
suite, protocol, and output-schema hashes. SQLite is rebuildable and is not qualification truth.
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
