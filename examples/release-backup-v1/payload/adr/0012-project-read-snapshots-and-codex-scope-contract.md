# ADR 0012: Project read snapshots and Codex scope contract

Status: Accepted

## Context

Milestone 5 needs a truthful, resumable packet from a bounded existing repository without turning repository text into instruction authority or adding premature artifact types.

## Options

1. Read on demand and retain only SQLite state.
2. Snapshot the full repository and create one artifact type per plan record.
3. Snapshot explicit reads in the generic object store, use three project artifacts, and make packet scope an exact authority contract.

## Decision

Use option 3. `ProjectEstateReader` reads normalized explicit paths and bounded two-level tree names. Raw bytes use `SourceObjectStore`. Milestone 5 adds only `project.map`, `project.charter`, and `project.codex_packet`. Evidence reads do not grant write authority. Result verification is reported unless PEOS executed it.

## Consequences

Facts are traceable, resume uses frozen bytes, prompt injection remains data, and accepted results create a superseding map without overwriting history. Repository comprehension stays deliberately shallow and target commands are not executed.

## What would change this decision

A verified need for semantic analysis, independently executed tool evidence, or separate lifecycle ownership for a nested project record requires a new ADR.
