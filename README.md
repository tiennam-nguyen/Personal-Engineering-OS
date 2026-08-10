# PEOS — Personal Engineering OS

**PEOS** is a local-first Personal Engineering Operating System for turning research, projects, learning, and model-assisted work into **durable, verifiable artifacts**.

Instead of treating chat history, a model provider, or a database as the source of truth, PEOS stores important state in canonical files with explicit provenance and verification evidence. SQLite is only a rebuildable projection.

PEOS v1.0.0 is designed for a **single user on a local machine** and works offline for its core operations.

---

## What PEOS does

PEOS provides three primary compilers:

- **Research Compiler** — turns local source material into traceable questions, claims, contradictions, and synthesis.
- **Project Compiler** — turns a project request and bounded repository evidence into an objective, requirements, architecture decision, walking-skeleton plan, and self-contained Codex packet.
- **Learning Compiler** — turns an observable capability goal and diagnostic evidence into a prerequisite-aware practice loop and multidimensional mastery evidence.

Around those compilers, PEOS provides:

- resumable, hash-chained workflow runs;
- immutable source objects;
- typed cross-workflow relations;
- graph traversal;
- model route evaluation and qualification;
- backup and restore;
- migration ruin gates;
- retention and quarantine-based garbage collection;
- workspace integrity diagnostics;
- rebuildable SQLite indexes;
- release-grade recovery tooling.

---

## Design principles

PEOS follows a few core rules.

### Files are the durable source of truth

Canonical artifacts, run evidence, source objects, protocols, evaluation assets, and other durable workspace files survive loss of SQLite.

SQLite exists for lookup, search, adjacency, and other derived projections.

If the index is lost, it can be rebuilt.

### Evidence is explicit

PEOS distinguishes between information that was:

- read from canonical evidence;
- executed and observed;
- inferred;
- assumed;
- still unknown.

Model output is not automatically treated as verified truth.

### Model providers are replaceable

Model requests are structured, auditable, budgeted, and tied to versioned protocols.

Routes must pass task-specific evaluation before normal use.

PEOS v1 ships with a **deterministic offline mock adapter only**. It does not claim real-model quality.

### Recovery is part of correctness

Runs can be inspected, verified, resumed, or cancelled from durable state.

Committed steps are not silently re-executed during resume.

Canonical data is committed before its SQLite projection.

### Destructive operations fail closed

Backups are verified before restore or destructive migration/GC operations.

Restore never overwrites an existing workspace.

GC quarantines eligible data rather than permanently purging it in v1.

---

# Release status

Current release:

```text
PEOS v1.0.0
```

Release tag:

```text
v1.0.0
```

The v1 release was verified with:

- the complete repository test suite;
- Ruff formatting and linting;
- mypy on normal, Linux, and Windows targets;
- backup/restore acceptance;
- migration compatibility with the Milestone 8 workspace format;
- quarantine-based GC;
- workspace doctor/security checks;
- wheel and sdist builds;
- isolated wheel installation;
- installed-package Research, Project, and Learning acceptance flows;
- SQLite deletion and rebuild;
- GitHub Actions quality and release-smoke jobs.

Detailed verification evidence is recorded in [PLAN.md](PLAN.md).

PEOS is **not currently published to PyPI or as a GitHub Release**. The tagged repository is the release source.

---

# Requirements

PEOS v1 is built around:

- Python 3.11;
- [uv](https://docs.astral.sh/uv/) for the locked development/runtime environment;
- a local filesystem;
- SQLite from the Python runtime.

Core PEOS behavior does not require a network connection.

---

# Installation

## Option 1 — Run from the tagged repository

```bash
git clone https://github.com/tiennam-nguyen/Personal-Engineering-OS.git
cd Personal-Engineering-OS
git checkout v1.0.0

uv sync --locked
uv run peos --version
```

Use `uv run peos` in place of `peos` in the examples below when running directly from the repository environment.

## Option 2 — Build and install the wheel

Build the release artifacts:

```bash
uv build
```

This produces the wheel and source distribution under `dist/`.

Install the wheel into the Python environment you want to use:

```bash
uv pip install --python /path/to/python dist/peos-1.0.0-py3-none-any.whl
```

Then verify the installed CLI:

```bash
peos --version
peos --help
```

The release acceptance suite verifies that the installed package runs from `site-packages`, independently of the source checkout.

---

# Fastest way to explore PEOS

The repository contains a synthetic release backup designed for experimentation.

Verify it first:

```bash
peos backup verify examples/release-backup-v1
```

Restore it to a **new path**:

```bash
peos backup restore examples/release-backup-v1 --to peos-demo
```

Then inspect the restored workspace:

```bash
peos --workspace peos-demo doctor
```

This is the easiest way to explore a workspace that already contains representative canonical state, protocols, evaluation assets, source objects, and qualification evidence.

The example contains synthetic data only.

---

# Start a new workspace

```bash
peos --workspace my-workspace init
peos --workspace my-workspace doctor
```

A PEOS workspace keeps its operational state below `.peos/` while canonical artifacts and workspace assets remain file-based and inspectable.

For model-backed workflows such as Research and Project compilation, the workspace also needs the appropriate versioned protocols, evaluation suites, and qualified route evidence. The release example is useful as a reference.

---

# Basic artifact operations

Create a durable concept:

```bash
peos --workspace my-workspace artifact create \
  --title "Concept" \
  --body "Durable idea" \
  --tag peos
```

Retrieve it:

```bash
peos --workspace my-workspace artifact get ARTIFACT_ID
```

Search locally:

```bash
peos --workspace my-workspace artifact search "durable"
```

Verify canonical integrity:

```bash
peos --workspace my-workspace artifact verify ARTIFACT_ID
```

Artifacts are stored canonically outside SQLite. Lookup and lexical search use the derived index.

---

# Runs: inspect, resume, cancel, verify

PEOS workflows are durable runs rather than opaque one-shot agent sessions.

Common lifecycle commands are:

```bash
peos --workspace WORKSPACE run inspect RUN_ID
peos --workspace WORKSPACE run resume RUN_ID
peos --workspace WORKSPACE run cancel RUN_ID
peos --workspace WORKSPACE run verify RUN_ID
```

Runs contain immutable inputs and evidence plus an append-only hash-chained journal.

A committed step is not re-executed merely because a run is resumed.

If a model call was started but its result was never durably captured, PEOS treats the outcome as unknown rather than automatically retrying a potentially duplicated external action.

---

# Research Compiler

The Research Compiler turns one to four local plain-text sources into traceable research artifacts.

Example:

```bash
peos --workspace WORKSPACE research compile \
  --question "Is it effective?" \
  --source inbox/a.txt \
  --source inbox/b.txt
```

You can intentionally stop after source ingestion:

```bash
peos --workspace WORKSPACE research compile \
  --question "Is it effective?" \
  --source inbox/a.txt \
  --source inbox/b.txt \
  --stop-after-step ingest-research-inputs
```

Then use the normal run lifecycle:

```bash
peos --workspace WORKSPACE run inspect RUN_ID
peos --workspace WORKSPACE run resume RUN_ID
peos --workspace WORKSPACE run verify RUN_ID
```

Use `--no-cache` when you explicitly want model extraction to bypass the workspace-local derived model cache.

## Research artifacts

The compiler produces canonical:

- `research.question`
- `research.source`
- `research.claim`
- `research.contradiction`
- `research.synthesis`

Raw source bytes are preserved as immutable content-addressed objects below:

```text
.peos/objects/sha256/
```

Claims retain exact source locators.

Synthesis is reconstructed from committed claims rather than trusted directly from model prose.

## Research limitations

PEOS v1 research compilation intentionally supports a narrow local plain-text path.

It does not currently provide:

- URL fetching;
- web crawling;
- PDF ingestion;
- OCR;
- semantic search;
- embeddings;
- broad natural-language contradiction reasoning;
- real model providers.

---

# Project Compiler

The Project Compiler converts a strict project request plus bounded repository evidence into a self-contained project execution packet.

Compile:

```bash
peos --workspace WORKSPACE project compile \
  --request-file REQUEST.json
```

Export the generated Codex packet:

```bash
peos --workspace WORKSPACE project export-codex PACKET_ARTIFACT_ID
```

Accept a reported implementation result:

```bash
peos --workspace WORKSPACE project accept-result \
  --packet PACKET_ARTIFACT_ID \
  --result-file RESULT.json
```

Compilation supports explicit stop points such as:

```text
snapshot-project-inputs
draft-project-charter
```

and supports `--no-cache` for model-call cache bypass.

## Project artifacts

The compiler produces exactly three primary canonical project aggregates:

- `project.map`
- `project.charter`
- `project.codex_packet`

Cross-workflow operations may additionally produce `project.adr`.

## Repository trust boundary

Project Compiler reads only an explicit bounded repository read set.

Each requested read carries a named question.

Repository source text is treated as **data**, not as PEOS control-plane instructions.

PEOS does not automatically:

- modify the target repository;
- invoke Codex;
- execute arbitrary shell commands;
- run the verification command contained in a Codex packet.

A submitted Codex/result manifest therefore records verification as **reported evidence** unless PEOS itself actually executed it through a separately verified execution boundary.

---

# Learning Compiler

The Learning Compiler converts an observable capability goal and deterministic diagnostic fixture into a prerequisite-aware practice plan.

Compile a goal:

```bash
peos --workspace WORKSPACE learn compile \
  --goal-file GOAL.json \
  --diagnostic-file DIAGNOSTIC.json
```

Record an attempt against the planned exercise:

```bash
peos --workspace WORKSPACE learn attempt \
  --goal GOAL_ARTIFACT_ID \
  --attempt-file ATTEMPT.json
```

Compilation may be paused after:

```text
freeze-learning-inputs
analyze-learning-gap
```

Inputs are frozen before analysis, so resume does not reinterpret modified or deleted original files.

## Learning artifacts

PEOS v1 uses three canonical learning aggregates:

- `learning.goal`
- `learning.attempt`
- `learning.mastery`

Cross-workflow operations may also create standalone `learning.exercise` artifacts.

## Mastery evidence

Mastery is not represented as one opaque score.

PEOS keeps five evidence dimensions distinct:

- recall;
- explanation;
- discrimination;
- application;
- retention.

A correct answer in the current session does **not** establish retention.

Same-session retention therefore remains:

```text
NOT_ASSESSED
```

until temporally separated evidence exists.

The current review scheduler uses a replaceable fixed-interval policy. Its next-review date is a recommendation, not proof of mastery.

## Answer verification

The v1 deterministic Learning Compiler supports:

- normalized exact-text verification;
- single-choice verification.

There is no semantic model grader and no global `mastered=true` shortcut.

---

# Cross-workflow graph

PEOS can connect durable Research, Project, and Learning artifacts through typed relations.

Create one of the supported deterministic bridges:

```bash
peos --workspace WORKSPACE crossflow bridge \
  --request-file REQUEST.json
```

Traverse the graph:

```bash
peos --workspace WORKSPACE graph ARTIFACT_ID --depth 1
```

## Canonical relation model

Relations live once in canonical artifact metadata.

A historical artifact may use an outgoing relation:

```json
{"rel": "derived_from", "target": "art_..."}
```

A newly created target may host an incoming relation:

```json
{"source": "art_...", "rel": "supports"}
```

This allows PEOS to represent a directed edge without rewriting historical canonical bytes.

Reverse graph navigation returns the **same directed canonical edge**. It does not persist a second inverse relation.

SQLite stores only rebuildable adjacency/backlink projections.

Before graph data is trusted, the derived row is checked against its canonical host.

## Supported v1 bridges

The deterministic Crossflow compiler supports:

- reported project failure → `learning.exercise`;
- `SUPPORTED` research claim → `project.adr`;
- exact learning prerequisite gap → `research.question`.

No model chooses these links.

There is no arbitrary semantic relation inference or graph database in v1.

---

# Model protocols, evaluation, and qualification

PEOS treats model behavior as versioned infrastructure rather than an implicit dependency.

Protocols are workspace assets registered by exact version and hash.

Normal model routes fail closed until the exact task/route combination has valid current qualification evidence.

Run an evaluation suite:

```bash
peos --workspace WORKSPACE eval run model.summarization.core \
  --provider mock \
  --model deterministic-concept-summary-v1 \
  --model-revision 1
```

Compare two evaluation runs:

```bash
peos --workspace WORKSPACE eval compare RUN_A RUN_B
```

## Qualification rules

Qualification is bound to the exact:

- task kind;
- route/model revision;
- evaluation suite;
- protocol hash;
- output-schema hash.

Changing those inputs invalidates stale qualification.

Evaluation calls always bypass the normal model cache.

A candidate can legitimately produce:

```text
evaluation run: SUCCEEDED
qualification: FAILED
```

That is a valid evaluation result, not an infrastructure error.

Required deterministic gates cannot be overridden by a quality/reference score.

A later valid `FAILED` evaluation can revoke an earlier qualification.

## Comparison reports

Comparison exposes raw evidence such as:

- deterministic gate results;
- reference-match numerators and denominators;
- provider-call count;
- input/output bytes;
- input/output token measurements;
- observed wall time where available;
- pricing status.

PEOS does not calculate a global “best model” score.

The bundled deterministic mock uses its explicitly labeled mock token measurement. It is not evidence of provider-native token usage or general model quality.

Monetary cost remains unknown when no verified price exists.

---

# Protocols

Versioned model protocols live in the workspace and are addressed by exact identity and hash.

Inspect them with:

```bash
peos --workspace WORKSPACE protocol list
peos --workspace WORKSPACE protocol verify NAME VERSION
```

Trusted instructions, user intent, untrusted source/context data, and output schemas remain separate channels.

Imported content cannot register protocols, routes, workflows, tools, or schemas.

---

# SQLite is disposable

SQLite is a derived projection.

The canonical workspace remains authoritative.

If the index is lost or intentionally removed, delete **only**:

```text
.peos/index.sqlite3
```

Then rebuild:

```bash
peos --workspace WORKSPACE index rebuild
```

Finally verify the workspace:

```bash
peos --workspace WORKSPACE doctor
```

Rebuild restores artifact lookup, relation projection, and other derived index state from canonical files.

Do not delete other files under `.peos/` as part of an index rebuild.

---

# Backup and restore

PEOS v1 provides a manifest-based, self-contained local backup format.

Create a backup:

```bash
peos --workspace WORKSPACE backup create \
  --output BACKUP
```

Verify it independently:

```bash
peos backup verify BACKUP
```

Restore it:

```bash
peos backup restore BACKUP \
  --to NEW_WORKSPACE
```

## Restore safety

Restore is intentionally conservative.

**Restore only to a new path.**

PEOS does not provide an overwrite/force restore path in v1.

A restored workspace rebuilds its derived SQLite state from canonical data.

Backup integrity is verified before restoration.

## What backups contain

Release backups preserve canonical workspace state required for recovery, including applicable:

- artifacts;
- source objects;
- run manifests, journals, inputs, outputs, and evidence;
- protocols;
- evaluation assets;
- ADRs;
- MAP and PLAN state;
- migration records;
- workspace configuration without materializing secret values.

SQLite, derived model cache, locks, and temporary staging state are not backup truth.

## Important privacy note

PEOS backups contain private workspace content.

Backup v1 is intentionally:

- uncompressed;
- unencrypted.

Protect a backup at least as strongly as the workspace it came from.

---

# Migration and retention

PEOS v1 includes release-hardening infrastructure for migration and retention.

Canonical migrations are guarded by verified backups tied to the exact pre-migration workspace generation.

Derived SQLite schema changes prefer rebuildable migration rather than modifying canonical intellectual state.

Retention and GC are deliberately conservative:

- canonical artifacts are retained;
- evidence needed for run/evaluation verification is retained;
- referenced source objects are retained;
- only provably disposable state may become a candidate;
- execution rechecks workspace state before acting;
- v1 moves eligible data into **quarantine** rather than permanently deleting it.

There is no permanent GC purge in v1.

Use the built-in command help for the exact migration/GC operations supported by your installed version:

```bash
peos --workspace WORKSPACE migrate --help
peos --workspace WORKSPACE gc --help
```

Operational recovery procedures are documented in [docs/recovery.md](docs/recovery.md).

---

# Workspace doctor

Run:

```bash
peos --workspace WORKSPACE doctor
```

`doctor` is a read-only integrity diagnostic.

It checks the relevant workspace state, including areas such as:

- configuration;
- canonical artifact integrity;
- relation integrity;
- run journals;
- source-object references;
- derived-index freshness;
- required protocol/workflow versions;
- evaluation/qualification evidence;
- migration records;
- lock state;
- control-plane secret leakage indicators.

Doctor reports problems; it does not silently repair canonical state.

Where applicable it provides the explicit recovery operation, such as rebuilding SQLite.

---

# Canonical, derived, and operational state

A useful mental model is:

## Canonical / durable

Examples include:

- artifact Markdown;
- immutable source objects;
- run manifests and frozen inputs;
- run evidence;
- append-only journals;
- protocols;
- evaluation suites and cases;
- canonical evaluation reports;
- cross-workflow relation metadata;
- migration records;
- workspace configuration.

## Derived / rebuildable

Examples include:

- `.peos/index.sqlite3`;
- model cache;
- graph adjacency/backlinks stored in SQLite.

## Operational

Examples include:

- workspace locks;
- staging directories;
- backup staging;
- GC plans and quarantine.

The exact ownership rules are documented in [MAP.md](MAP.md).

---

# Security and trust model

PEOS v1 is designed for a trusted local user operating a local workspace.

It protects primarily against:

- accidental corruption;
- stale derived state;
- duplicated workflow execution;
- malformed persisted state;
- unsafe restore/migration/GC boundaries;
- source/model prompt injection crossing into the control plane.

It does **not** claim protection against an attacker who fully controls the workspace and can rewrite both data and integrity metadata.

Other important limits:

- backups are not encrypted;
- there is no cloud backup or remote synchronization;
- mutation locking is local-machine only;
- there is no multi-user authorization system;
- secret scanning is not exhaustive;
- there is no real model-provider credential integration in v1.

See [docs/security.md](docs/security.md) for the full trust model and residual risks.

---

# Offline and model limitations

PEOS core operations work locally and do not require a model provider.

PEOS v1 does not include:

- OpenAI/Anthropic/Gemini/etc. provider integration;
- provider credentials;
- network model fallback;
- model-as-judge evaluation;
- web research;
- PDF/OCR ingestion;
- semantic/vector search;
- cloud synchronization;
- multi-device coordination;
- a server or daemon;
- a GUI.

The bundled deterministic mock exists to verify architecture, contracts, recovery, budgeting, evaluation, and routing behavior.

It is **not evidence of real-world model quality**.

---

# Repository structure

At a high level:

```text
src/peos/
├── domain/        # Pure domain values, validation, invariants
├── ports/         # Storage/model/index boundaries
├── application/   # Orchestration and verification
├── adapters/      # Filesystem, SQLite, deterministic mock
├── workflows/     # Fixed registered workflows
├── cli/           # CLI parsing/rendering
└── bootstrap.py   # Concrete dependency wiring

protocols/         # Versioned model protocols
evals/             # Canonical evaluation suites and goldens
adr/               # Architecture decision records
examples/          # Synthetic release backup and fixtures
docs/              # Recovery, security, release procedures
tests/             # Unit/integration/architecture verification
```

For the detailed system topology, see [MAP.md](MAP.md).

---

# Development

Synchronize the locked environment:

```bash
uv sync --locked
```

Run the test suite:

```bash
uv run --locked pytest
```

Run the complete quality gate:

```bash
uv lock --check
uv run --locked ruff format --check .
uv run --locked ruff check .
uv run --locked mypy
uv run --locked mypy --platform linux
uv run --locked mypy --platform win32
uv run --locked pytest
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for focused test commands and release procedures.

---

# Documentation

Start here depending on what you need:

- [README.md](README.md) — product overview and user commands.
- [MAP.md](MAP.md) — current architecture and ownership map.
- [PLAN.md](PLAN.md) — implementation and verification ledger.
- [CONTRIBUTING.md](CONTRIBUTING.md) — development and verification workflow.
- [docs/recovery.md](docs/recovery.md) — backup, restore, migration, index, and recovery operations.
- [docs/security.md](docs/security.md) — trust boundaries, security controls, and limitations.
- [docs/RELEASE_CHECKLIST.md](docs/RELEASE_CHECKLIST.md) — v1 release acceptance procedure.
- [adr/](adr/) — accepted architecture decisions.

---

# Release guarantees and non-guarantees

PEOS v1.0.0 has been exercised through a clean-install release acceptance path covering:

```text
install package
→ verify backup
→ restore workspace
→ run Research Compiler
→ run Project Compiler
→ run Learning Compiler
→ verify runs/artifacts
→ delete SQLite
→ rebuild SQLite
→ run workspace doctor
```

That establishes the release's local recovery and execution contract.

It does **not** establish:

- general AI/model quality;
- security against a malicious workspace owner;
- encrypted backups;
- multi-user or distributed correctness;
- cloud availability;
- public-package supply-chain guarantees;
- semantic correctness outside the explicit deterministic/reference verification procedures implemented by PEOS.

---

# Current scope

PEOS v1.0.0 is intentionally:

- local-first;
- single-user;
- file-canonical;
- SQLite-projected;
- offline-capable;
- deterministic where possible;
- fail-closed around durable state;
- provider-independent at the architecture boundary.

The nine-milestone v1 implementation campaign is complete.

Future work should be driven by real operational use, measured friction, and recorded evidence rather than by adding features for completeness.