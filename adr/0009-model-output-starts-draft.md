# ADR-0009: Model output starts as draft

Status: Accepted

Date: 2026-08-05

## Context

A generating model cannot be the only authority for accepting its own factual or consequential
output.

## Decision

Model-produced artifacts begin as drafts; promotion needs policy, deterministic verification, or
human review.

## Consequences

Automation may stop at review boundaries, but unverified knowledge cannot silently become trusted.

## Alternatives considered

Auto-accepting generated artifacts violates the independent-verification invariant.

## Revisit trigger

Artifact-specific evidence proves a safe auto-acceptance policy.
