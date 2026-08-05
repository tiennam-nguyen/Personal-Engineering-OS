# ADR-0006: Deterministic model routing policy

Status: Accepted

Date: 2026-08-05

## Context

Provider selection must respect cost, sensitivity, and capability budgets.

## Decision

Configuration selects model routes; a model cannot self-select unrestricted providers.

## Consequences

Routing is inspectable and bounded; adaptive behavior remains deferred.

## Alternatives considered

An autonomous router cannot independently prove budget compliance; always choosing the strongest
model disregards cost policy.

## Revisit trigger

Eval evidence shows adaptive routing improves quality/cost without violating budgets.
