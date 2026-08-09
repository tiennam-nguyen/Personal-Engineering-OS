# Plan

## Milestone 5 — Project Compiler

State: locally implemented; remote promotion remains unverified.

- Baseline: `13e42158d56f60f1494a19d4d966b15e458ccd05` on `main`, clean; 116 tests collected and baseline locked pytest exited 0.
- Surface: strict request/result, bounded estate snapshots, protocol/model/cache, deterministic L0–L3 map, aggregate charter, packet, resume/cancel/verify, result-map update, CLI, guards, ADR 0012.
- Focused evidence: project domain/estate/workflow/CLI/cancellation/architecture group completed 16 tests with exit 0; focused durable result-run/model-resume/CLI regression completed 4 tests with exit 0.
- Final local gate: `git diff --check`, `uv lock --check`, Ruff format/check, normal/Linux/Windows mypy, Python pytest, locked pytest, and collect-only all exited 0. Mypy checked 116 source files on each target; Python pytest reported `125 passed in 118.69s`; locked pytest reported `125 passed in 132.52s`; collect-only inventoried 125 tests.
- Injection/scope: a fixture README contains scope-widening text but stays forbidden and outside Allowed; an out-of-scope result fails before map creation.
- Recovery/cache: snapshot stop/resume reuses objects; equivalent input cache hit reports zero provider calls; cancellation is idempotent and verifies.
- Result: accepted `src/app.py` bytes create a new map, preserve the old map, and label verification `reported`.
- Process smokes: compile run `run_5e016fee1e1e4d82b6290c653916c0d3` verified and packet reconstruction survived SQLite rebuild (`artifacts_indexed: 3`); result run `run_12afe8900ead40d0a1f0d119b2c337b2` committed two steps and independently verified. Exact-byte cache hit used zero provider calls; bypass used one.
- Remote CI: `[UNKNOWN]` until an authorized Milestone 5 commit is pushed and Actions is observed on its exact SHA.
- Milestone 6 frontier: Learning Compiler only after Milestone 5 promotion; no Milestone 6 code exists here.

## Mission

Build PEOS milestone by milestone without making durable work dependent on a provider, projection
database, or opaque agent context.

## Milestone 0 — Repository constitution

Status: `COMPLETE`.

Allowed files: repository metadata, package marker, architecture guard, CI, maps, plan, ADRs,
and contributing documentation.

Forbidden scope: CLI behavior; artifacts or canonical-store implementation; SQLite; workflows;
model/tool adapters; schemas; migrations; packaging/release behavior; any Milestone 1+ feature.

Required behavior: a fresh checkout can synchronize declared dependencies and run one command that
executes the architecture guard and test suite.

Acceptance command: `uv run --locked pytest`

Supporting gates: `uv run --locked ruff format --check .`, `uv run --locked ruff check .`, and
`uv run --locked mypy`.

Recovery/rollback: all changes are text/configuration only. No existing canonical data exists and
no destructive PEOS operation is introduced.

## Verification ledger

- [READ] GitHub Actions failed at Linux mypy due to an improperly narrowed Windows-specific
  `msvcrt` branch. Remote CI is not yet verified green for the repaired commit.

- [RAN] `python --version` -> `Python 3.11.7`.
- [RAN] `git --version` -> `git version 2.51.0.windows.2`.
- [RAN] Before installation, `uv --version` was unavailable and Python had no pytest, Ruff, or
  mypy module.
- [RAN] Official uv installer for `0.11.32` completed and installed `uv.exe`, `uvx.exe`, and
  `uvw.exe` in `C:\Users\LOQ\.local\bin`.
- [RAN] `uv lock` -> `Resolved 13 packages in 937ms` using CPython 3.11.9 at
  `C:\Users\LOQ\AppData\Local\Programs\Python\Python311\python.exe`; committed `uv.lock`.
- [RAN] `uv sync --locked` -> created `.venv`, built `peos`, and installed the 13 locked packages,
  including `mypy==1.20.2`, `pytest==9.1.1`, and `ruff==0.16.1`.
- [RAN] `ruff format --check .` -> `17 files already formatted`.
- [RAN] `ruff check .` -> `All checks passed!`.
- [RAN] `python -m mypy` in `.venv` -> `Success: no issues found in 2 source files`.
- [RAN] `python -m pytest` in `.venv` -> `4 passed in 0.04s`.
- [RAN] `uv run --locked pytest` -> `4 passed in 0.03s`.

## Milestone 1 — artifact round trip

Status: `COMPLETE` pending final packet verification transcript.

Delivered: one `knowledge.concept` schema; Markdown/YAML canonical files; independent SHA-256
verification; atomic staging; SQLite projection; exact lookup; lexical search; dirty-index marker;
rebuild; argparse CLI; integration coverage.

Residual risks: single-writer only; best-effort durability only; LIKE search is intentionally
simple.

## Stop conditions

Stop AMBER/RED if a destructive operation lacks recovery; source cannot be read; the map conflicts
with the repository; acceptance cannot be verified; a non-negotiable would be broken; scope must
expand; an external API is unverified; or two milestones in sequence require plan surgery.

## Assumption ledger

1. [ASSUMED] Python 3.11 is an acceptable initial runtime because it is installed locally and the
   spec asks for a modern supported Python runtime. Cheapest falsifier: user selects another
   language/runtime before Milestone 1.
2. [ASSUMED] uv is acceptable as the single lockfile-based environment manager. Cheapest
   falsifier: a fresh checkout cannot resolve and run the committed lockfile.
3. [ASSUMED] GitHub Actions is the intended CI host. Cheapest falsifier: user names another CI
   host before CI is relied on.
## Milestone 2 — run journal and resumable deterministic workflow

Status: `GREEN` in the uncommitted working tree.

Delivered immutable run files, append-only journal/replay, deterministic two-step workflow,
test-only fault injection, recovery reconciliation, cancellation, cross-platform mutation lock,
and JSON CLI.

Verification evidence:

- [RAN] Ruff format/check passed; mypy found no issues in 48 source files.
- [RAN] `python -m pytest` and `uv run --locked pytest`: `77 passed` each.
- [RAN] collect-only: artifact 8; Milestone 1 CLI 2; cancellation 10; run CLI 12;
  crash boundaries 10; repository/lock 5; architecture 7; journal 18; state 2; workflow 3.
- [RAN] real Windows subprocess contention blocked a second mutator; process death released the
  byte lock; inspect/verify remained available while it was held.
- [RAN] all nine crash checkpoints passed recovery tests.
- [RAN] stop/resume `run_b4a6bdd81a124cd3bfd386f3ba1605e6`, step
  `step_40c5347c8399e1e17417afd606681ece`: execution count `1 -> 1`, sequences `11 -> 26`, output
  `art_6e496dd6afbf3a0bfe0230a309bf0e4a` at
  `sha256:91924ad04d999fdf2421a9be202fb955a67c77fb299da00cbfd96b90ad8a6ba5`.
- [RAN] cancellation `run_4f619b7ce4b940f894fcd1db29eb794a`: inspect/verify CANCELLED;
  resume exit 4 without traceback; event count `12 -> 12`.

Residual assumptions: OS locking is local-machine only; power-loss behavior beyond tested fsync
boundaries is unknown; the hash chain detects accidental corruption, not hostile workspace control.

Milestone 3 frontier only: versioned protocol registry; context manifest/compiler; deterministic mock
model gateway; request/response audit; budget and cache contracts.

## Milestone 3 — protocol registry and deterministic mock workflow

Status: `GREEN` in the uncommitted working tree, subject to the final verification transcript.

Delivered the strict protocol registry, verified-context compiler, structured model contracts,
mock-only route, labeled accounting and budgets, hashed derived cache, immutable call audits, model
journal events, canonical-first workflow, inspect/verify, protocol CLI, bypass, and resume without
repeating a committed call. Added focused protocol, context, contracts, budget, mock, cache, and
workflow tests.

CLI evidence: protocol hash `sha256:e3413a67718d47e69a3cfbb2f30c33d5e38bccf3be496f1010fe283abafffa73`;
miss `run_8ea39d263b864b2394c382a6ce62ad3f` called once; equivalent hit
`run_b5221369686a4fd1a535a2ceff94fd57` called zero times with origin provenance; bypass
`run_c4b73b4029904bc8948160446a14e42c` called once. Fresh stopped run
`run_74fb2c333fbb41fa961be9bb0fa0cf0e` kept call-start count `1 -> 1` and verified output
`art_009c9a9449fd0667b797e70b0c1ae6de`.

Residual risks: mock output is not real-provider quality; mock tokens are not provider-native;
route has no fallback; retrieval remains lexical; cache has no GC; fsync cannot prove every power
loss boundary; hashes do not defend against a hostile workspace owner.

Milestone 4 frontier only: Research Compiler vertical slice. No Milestone 4 behavior is implemented.

## Milestone 4 — plain-text Research Compiler

Status: `GREEN` in the uncommitted working tree, subject to the final verification transcript.

Delivered `research.compile-plain-text@1.0.0`, immutable raw source objects, five research artifact
types, strict payloads/links, exact UTF-8 line coverage, deterministic claim extraction,
same-key/polarity evidence merging, opposite-polarity contradictions, traceable synthesis, research
events/evidence, ordered canonical-first commits, inbox-independent resume, cancellation, cache
reuse/bypass, inspect/verify, search and rebuild support, and JSON CLI.

Acceptance evidence: run `run_f856e26728e845b2b9c4510ba8a95fc9` preserved four objects, produced
10 research artifacts, recorded five readable and one unreadable segment, merged the two positive
locators, retained one negative locator, produced one contradiction, and verified before and after a
10-artifact SQLite rebuild. Equivalent extraction was a cache hit with zero calls; bypass called
once. Resume run `run_8db2c13c2ed54f90a2b6f7cb5caa7ffd` succeeded after inbox deletion,
kept source artifact bytes unchanged, and retained ingest execution count one.

Residual risks: the line grammar is deliberately narrow; contradiction detection handles only
shared normalized keys and standalone `not`; locators are line-only; invalid UTF-8 excludes a whole
line; no source weighting, human promotion, semantic retrieval, or object GC exists.

Milestone 5 frontier only: Project Compiler vertical slice. No Milestone 5 behavior exists.
