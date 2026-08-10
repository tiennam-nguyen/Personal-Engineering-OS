# ADR-0004: Typed workflows in code before a DSL

Status: Accepted

Date: 2026-08-05

## Context

Workflow behavior must be inspectable and testable without creating a hidden programming language.

## Decision

Use typed Python definitions and YAML configuration; do not introduce a workflow DSL.

## Consequences

Advanced customization requires code changes, which keeps control flow and verification explicit.

## Alternatives considered

YAML DAGs and general agent loops introduce condition and execution semantics before evidence of a
stable shared grammar.

## Revisit trigger

Three or more stable repeated workflow patterns plus non-programmer authoring demand.
