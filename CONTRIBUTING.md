# Contributing

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
