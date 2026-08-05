# Plan

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

## Milestone 1 frontier

Implement only the artifact round trip: workspace initialization, one typed artifact, atomic
canonical write, SQLite projection, exact lookup, lexical search, independent hash verification,
and rebuild-after-index-deletion. Required failure cases: malformed artifact, duplicate ID, and
projection failure after canonical commit.

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
