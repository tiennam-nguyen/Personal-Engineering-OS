# ADR-0003: Stable artifact identifiers independent of paths

Status: Accepted

Date: 2026-08-05

## Context

Moving or renaming an artifact must not change its durable identity or break provenance.

## Decision

Use opaque time-sortable identifiers or an equivalent scheme; paths are presentation only.

## Consequences

Links remain stable across layout changes; users cannot rely on a slug as an identity.

## Alternatives considered

Slug/path identity breaks on moves; content-hash identity changes whenever content is revised.

## Revisit trigger

A verified synchronization requirement needs another identity scheme.
