# ADR-0002: Canonical files and rebuildable SQLite projection

Status: Accepted

Date: 2026-08-05

## Context

Durable knowledge must remain readable and recoverable if an index or application binary is lost.

## Decision

Human-readable versioned files own durable artifact state; SQLite is a disposable projection.

## Consequences

The system pays for projection rebuild and consistency checks, but canonical files win on conflict.

## Alternatives considered

SQLite/PostgreSQL canonical storage couples recovery to database behavior; an event log alone is
not the specified readable artifact form.

## Revisit trigger

Verified transaction/query requirements make canonical files unreliable.
