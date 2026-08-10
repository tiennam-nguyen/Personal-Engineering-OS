# ADR-0010: Lexical search is mandatory; embeddings are optional

Status: Accepted

Date: 2026-08-05

## Context

Core retrieval must work offline and derived state must be rebuildable.

## Decision

Provide lexical full-text retrieval as the baseline; treat embeddings as optional projections.

## Consequences

The initial system remains useful without a model or vector database; semantic retrieval may be
added only as a replaceable adapter.

## Alternatives considered

Vector-only search makes core retrieval dependent on non-baseline infrastructure.

## Revisit trigger

Measured corpus evidence shows lexical search cannot satisfy core retrieval needs.
