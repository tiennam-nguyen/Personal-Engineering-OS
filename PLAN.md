# Plan

## Milestone 7 — Cross-Workflow Graph

State: implementation commit promoted; final documentation commit and exact-SHA CI observation
remain pending.

- Baseline: M6 final SHA `a5f1ac9d1517befc44b590b299073d47920dd1b7`, clean `main`, 139
  tests collected, baseline locked pytest exit 0; GitHub Actions run `31309992295` independently
  observed `success` on the same SHA.
- Surface: strict incoming/outgoing link union, deterministic hosted edges, SQLite relation
  projection with host revision, verified bidirectional traversal, two new artifact types, one
  three-operation crossflow workflow, frozen-input recovery, cancellation, CLI, and ADR 0014.
- Focused evidence: Ruff/mypy GREEN on 148 source files; 19 focused relation/graph/crossflow/CLI/
  architecture tests exited 0. Canonical-commit recovery preserved target bytes and repaired the
  relation projection.
- Acceptance smoke: Research, Project, and Learning sources were produced through existing
  services. Bridge runs `run_e287f099f8114e3b8014635609982fb8`,
  `run_f22ed279bb6842d08fbb8ec9431375af`, and
  `run_55624f4b6f794dd783b12293056d4d2d` all verified. Six endpoint graph queries exposed identical
  directed edge tuples in reverse navigation; depth two reached claim→ADR→charter.
- Rebuild smoke: deleting only the derived index then rebuilding indexed 11 artifacts; graph
  summaries before/after were equal and all three bridge runs verified afterward.
- Recovery/cancellation: `run_212f4cfd9f4d4a21b6631691f3479839` resumed after request deletion,
  source hash stayed unchanged, and Step 1 execution remained one in the ID-specific regression
  assertion. Cancelled `run_4eaeeb4a0704461eba874c0208dcb7f3` verified, repeated cancel kept
  event count `11 -> 12 -> 12`, and resume exited 4 without traceback.
- Final local gate: `git diff --check`, `uv lock --check`, Ruff format/check, normal/Linux/Windows
  mypy, Python pytest, locked pytest, and collect-only all exited 0. Mypy checked 148 source files;
  Python pytest reported `148 passed in 163.79s`; locked pytest reported
  `148 passed in 169.03s`; collect-only inventoried 148 tests.
- Residual risks: incoming metadata is a new persisted format; SQLite can become dirty and requires
  explicit rebuild; traversal is structural rather than semantic; reported failures remain
  externally asserted evidence.
- Assumptions: none added.
- Remote CI: implementation commit `527c9f4e9e102b68bd4948ba6fe0ebbf90576c5f` was observed GREEN
  in GitHub Actions run `31312382881`; the quality job completed in 51 seconds after locked sync,
  Ruff format/check, mypy, and locked pytest all succeeded.
- Milestone 8 frontier: Evaluation and Routing Qualification only after M7 promotion.

## Milestone 6 — Learning Compiler

State: implementation commit promoted; final documentation commit and exact-SHA CI observation
remain pending.

- Baseline: `c313d975320a220b0a9e1d3c0c06044e50e1f229` on `main`, clean; 125 tests collected and baseline locked pytest exited 0.
- Surface: deterministic goal compilation and attempt recording, exact three-artifact aggregate,
  cycle rejection, diagnostic gaps, first exercise and future events, five mastery dimensions,
  fixed review policy, frozen-input resume, cancellation, independent verification, CLI, index
  rebuild compatibility, architecture guards, and ADR 0013.
- Focused evidence: Ruff and mypy passed; learning resume/cancellation plus Project CLI regression
  group completed six tests with exit 0.
- Final local gate: `git diff --check`, `uv lock --check`, Ruff format/check, normal/Linux/Windows
  mypy, Python pytest, locked pytest, and collect-only all exited 0. Mypy checked 134 source files on
  each target; Python pytest reported `139 passed in 151.93s`; locked pytest reported
  `139 passed in 139.42s`; collect-only inventoried 139 tests.
- Acceptance smoke: compile `run_473fcdad14c74ba3a94bbd12feebbdb0` selected
  `binary-search-interval` / `exercise-interval-1`; attempt
  `run_521a04b01f334281aeed167834cabd8b` demonstrated explanation while retention remained
  `NOT_ASSESSED`; both independently verified. Deleting the derived index and rebuilding indexed
  three canonical learning artifacts; both runs verified afterward.
- Recovery smoke: compile `run_f125ea1f9e284784abee4d130f57fce1` resumed from frozen inputs after
  the goal file was deleted and diagnostic file changed. Cancelled run
  `run_2fe2c887e9164ed7ae99f814bdded656` verified, event count stayed `11 -> 12 -> 12` across repeated
  cancel, and resume failed safely with exit 4.
- Remote CI: implementation commit `4d9191269e77d7f6af1ef942d4a6f63942bb3001` was observed GREEN
  in GitHub Actions run `31309938604`; the quality job completed in 44 seconds after locked sync,
  Ruff format/check, mypy, and locked pytest all succeeded.
- Milestone 7 frontier: cross-workflow graph only after Milestone 6 promotion; no Milestone 7 code
  is included here.

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

## Milestone 8 — evaluation and routing qualification

Status: `GREEN`. Implementation commit `4fb18a68c8ef227fe3c5a0a41e3ba5c722b728d0` passed
GitHub Actions run `31319661581` (`quality`, success). The final local gate recorded 183 tests in
both bare-Python and locked environments, 168 mypy source files on normal/Linux/Windows targets,
188 Ruff-formatted files, and a 183-test collect-only inventory.

Delivered committed static qualification suites for all three production model tasks, exact
route/suite/protocol/schema authorization, deterministic and reference scoring, canonical eval
reports, comparison without an overall-winner claim, per-case durable resume, unknown-outcome
fail-closed behavior, cancellation, report re-derivation, stale-policy invalidation, and
SQLite-loss recovery.

Deliberate sacrifices: mock candidates only; exact static goldens; deterministic `1.0` conformance
threshold; cache bypass; no retry, real-provider quality claim, pricing, statistical judge,
cross-suite ranking, or threshold tuning from observed results.

Milestone 9 frontier only: release hardening and end-to-end packaging. Do not add new model tasks,
provider integrations, or evaluation policy in that milestone without a new decision.
