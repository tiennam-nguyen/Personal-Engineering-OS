# Repository Map

## L0 — purpose and evidence

[READ] The governing specification is `PEOS_Architecture_Implementation_Spec_v0.1.md`, read in
full before this constitution was created. PEOS is planned as a local-first, single-user,
offline-capable Python modular monolith. Its canonical intellectual state must remain independent
of providers, SQLite, and a context window.

[READ] Repository state at constitution start: an empty Git worktree with no commits and no
existing package or manifest.

## L1 — current topology

```text
pyproject.toml              project metadata and quality-tool configuration
src/peos/__init__.py        package marker; no runtime behavior
tests/unit/test_architecture.py
                            dependency-direction architecture guard
adr/                        durable decisions and ADR template
.github/workflows/ci.yml    CI quality gates
MAP.md / PLAN.md            recovery-oriented project state
```

Directories named in the specification but not needed for Milestone 0 (`application`, `domain`,
`ports`, `adapters`, `workflows`, `protocols`, `evals`, and artifact storage) are deliberately
absent. Their absence prevents a false claim that Milestone 1 or later behavior exists.

## L2 — dependency direction (planned contract)

```text
cli -> application -> domain
                 -> ports <- adapters
workflows -> application, domain, ports
bootstrap composes adapters at the edge
```

`domain` never depends on an adapter, CLI, database, filesystem package, or model SDK. Cross-
workflow communication will use artifacts and application services, never direct workflow calls.

## L3 — entry points and verification

[READ] There is no PEOS runtime entry point in this milestone.

[RAN] The architecture guard is collected by pytest: `4 passed in 0.04s`. The full toolchain
transcript is recorded in `PLAN.md`.

## Invariants carried forward

- Canonical files, not SQLite or caches, own durable state.
- IDs are opaque and path-independent; provenance is mandatory from the first artifact release.
- Canonical writes must be atomic or recovery-manifested; destructive actions need dry run,
  approval, and a verified recovery path.
- Imported material is data, never executable instruction authority; secrets do not enter normal
  artifacts or logs.
- Model outputs start as drafts and cannot be their own only verifier.
- Workflows remain typed code; configuration cannot become a general expression language.
- A cold-started maintainer can continue from repository artifacts alone.
