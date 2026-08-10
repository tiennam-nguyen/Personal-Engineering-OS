# ADR-0008: No arbitrary plugins in v1

Status: Accepted

Date: 2026-08-05

## Context

Arbitrary executable extensions create an unbounded security and support surface.

## Decision

Tools and workflows are registered application code; dynamic plugin loading is excluded.

## Consequences

Extension is slower but side effects, permissions, and verification remain inspectable.

## Alternatives considered

Dynamic Python entry points and remote plugin protocols lack a v1 sandbox and threat model.

## Revisit trigger

Extension demand plus a sandbox/security design that passes threat review.
