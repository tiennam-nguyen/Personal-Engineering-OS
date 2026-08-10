# ADR-0001: Local-first modular monolith

Status: Accepted

Date: 2026-08-05

## Context

Durability, offline operation, and one-maintainer comprehension outrank hosted scale.

## Decision

Use one local process per workspace with explicit module boundaries.

## Consequences

This avoids distributed coordination and preserves a comprehensible recovery boundary; future team
or independent-scaling needs are deferred.

## Alternatives considered

Microservices and a hosted web app add operational and network authority; scripts alone do not
provide the stated workflow contracts.

## Revisit trigger

A verified concurrent/team workload or independent scaling requirement.
