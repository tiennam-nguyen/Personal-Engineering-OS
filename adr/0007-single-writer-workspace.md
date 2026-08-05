# ADR-0007: Single-writer workspace

Status: Accepted

Date: 2026-08-05

## Context

Canonical mutation needs a simple, recoverable atomicity model for one user and one machine.

## Decision

Permit one mutating process per workspace while allowing concurrent reads.

## Consequences

A workspace lock and stale-lock recovery are required; simultaneous writers are not supported.

## Alternatives considered

Distributed locks, CRDTs, and server authority add unverified collaboration complexity.

## Revisit trigger

A verified multi-process or multi-user editing requirement.
