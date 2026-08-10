# ADR-0005: Protocols are versioned workspace assets

Status: Accepted

Date: 2026-08-05

## Context

Model instructions affect outputs and must be auditable independently of provider state.

## Decision

Store protocols as versioned workspace files and record their hashes for model calls.

## Consequences

Prompt changes are reviewable artifacts; imported text cannot gain protocol authority.

## Alternatives considered

Embedded prompt strings and provider-managed assistants obscure the durable instruction asset.

## Revisit trigger

None expected beyond storage-detail changes.
