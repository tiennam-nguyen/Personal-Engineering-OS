# Contributing

## Learning Compiler verification

```text
uv run --locked pytest tests/unit/test_learning_model.py tests/unit/test_learning_diagnostic.py tests/unit/test_learning_graph.py tests/unit/test_learning_mastery.py tests/unit/test_learning_artifacts.py -q
uv run --locked pytest tests/integration/test_learning_workflow.py tests/integration/test_learning_resume.py tests/integration/test_learning_cancellation.py tests/integration/test_learning_cli.py -q
uv run --locked pytest tests/unit/test_architecture.py -q
```

Use a temporary initialized workspace for real CLI smoke. Exercise the acceptance fixture through
compile, inspect, verify, artifact lookup, exact-revision attempt, and mastery lookup. Then remove
only the resolved workspace's derived `.peos/index.sqlite3`, rebuild it, and repeat lookups and run
verification. Resume smoke must modify or delete external JSON after its frozen-input step;
cancellation smoke must prove a cancelled run cannot resume and repeated cancellation appends no
event. Expected CLI failures must return a stable error without a traceback.

Learning tests must cover empty/invalid references, duplicate identifiers, self/two-node/longer
cycles, diagnostic pass/fail/not-assessed, deterministic gap ordering, time-budget behavior,
exact-text normalization, single-choice option validation, stale goal revisions, five separate
mastery dimensions, same-session retention, fixed review dates, canonical-first recovery, and
SQLite rebuild. Do not add a model route, model cache, scalar mastery, or a fourth learning artifact
type.

## Project Compiler verification

```text
uv run --locked pytest tests/unit/test_project_artifacts.py -q
uv run --locked pytest tests/integration/test_project_estate_reader.py -q
uv run --locked pytest tests/integration/test_project_workflow.py -q
uv run --locked pytest tests/integration/test_project_cli.py -q
uv run --locked pytest tests/integration/test_project_cancellation.py -q
uv run --locked pytest tests/unit/test_architecture.py -q
```

Use a temporary PEOS workspace and a separate temporary target repository. Cleanup only exact resolved fixture paths after confirming `peos.yaml`; never recursively remove a computed workspace/repository root. Cover domain/artifacts, estate reads, deterministic mock/cache, resume, result scope, cancellation, JSON CLI, architecture, and Linux/Windows mypy.

## Toolchain

[READ] This project uses Python 3.11, `uv`, pytest, Ruff, and mypy. Package bounds live in
`pyproject.toml`; `uv.lock` is the reproducible resolution record.

The commands below use the project environment. `uv sync --locked` creates or synchronizes the
environment only from the committed lockfile. `uv run --locked` rejects an out-of-date lockfile.

## Fresh checkout

```powershell
uv sync --locked
uv run --locked pytest
```

The second command is Milestone 0's single acceptance command: it executes the architecture
guard and any test files. It must have recorded successful output before a completion claim.

## Quality gates

```powershell
uv run --locked ruff format --check .
uv run --locked ruff check .
uv run --locked mypy
uv run --locked pytest
```

## Dependency-direction rule

The architecture guard in `tests/unit/test_architecture.py` is intentionally small at this
milestone. It scans `src/peos/domain`, `src/peos/application`, `src/peos/workflows`, and
`src/peos/cli` if those directories exist. Future implementation must extend the same guard when
adding a boundary, rather than bypassing it.

- `domain` must not import adapters, CLI, model SDKs, filesystem, or database packages.
- `application` may import only `domain` and `ports` within PEOS.
- `workflows` may import `domain`, `application`, and `ports`, not adapters.
- `adapters` implement ports; external packages stay there.
- `cli` may use application DTOs and bootstrap wiring, not adapter internals.
- Circular imports are forbidden.

No package installation command is treated as verified merely because it is documented. The
Milestone 0 command transcript records the installed resolver's actual result.
## Run workflow verification

Use focused locked tests for run state/journal/sample workflow, `test_run_repository.py`,
`test_run_crash_boundaries.py`, `test_run_cancellation.py`, and `test_run_cli.py`, then run:

```powershell
git diff --check
uv lock --check
ruff format --check .
ruff check .
python -m mypy
python -m pytest
uv run --locked pytest
```

Fault injection is test-only. Windows contention is verified with real subprocesses using
`msvcrt.locking`; closing the process-held handle releases the lock. POSIX uses `fcntl.flock`.
CLI smoke workspaces must be temporary, outside the repository, and checked for `peos.yaml` before
deleting only their exact resolved paths.

## Protocol/model verification

Run focused protocol, context, contract, mock, budget, cache, workflow, event/resume, CLI, and
architecture tests before the full suite. The production registry is mock-only: do not add provider
SDKs, HTTP clients, credentials, fallback, or automatic retry. CLI smoke must demonstrate miss,
equivalent hit with zero call events, `--no-cache`, and stopped-step resume.

The final gate includes normal mypy, `uv run --locked mypy --platform linux`,
`uv run --locked mypy --platform win32`, both Python and locked pytest, and collect-only inventory.

## Research Compiler verification

Run research artifact, extraction, normalization, synthesis, object-store, mock extractor,
workflow, resume, cancellation, CLI, event and architecture tests. Invalid UTF-8 fixtures must be
written as raw bytes, never through replacement decoding. The acceptance fixture uses LF and CRLF
for the two semantically identical supporting sources so their required raw hashes remain distinct.

The real smoke must verify source objects/locators, merged evidence, contradiction and synthesis;
delete and rebuild only the derived SQLite index; then demonstrate inbox-independent resume,
cache hit with zero calls, and `--no-cache`. Finish with the complete normal/Linux/Windows mypy,
Python/locked pytest, Ruff and lockfile sequence.
