# ADR 0011: Content-addressed sources and line-locator research commits

Status: Accepted

## Context

Plain-text research needs durable source evidence, exact citations, and recovery across multiple
canonical outputs without making SQLite authoritative.

## Decision

Preserve raw inputs as immutable SHA-256-addressed objects under the workspace. Cite decoded text
with one-based line numbers and exact byte half-open offsets; invalid UTF-8 makes the whole line
unreadable. Commit research artifacts in deterministic order with canonical save and verification
before each SQLite projection. Recovery reconciles identical outputs and continues at the first
unresolved artifact; it does not promise all-or-nothing multi-artifact visibility.

## Consequences

Source evidence survives inbox deletion and locators are independently verifiable. Line locators do
not represent pages, timestamps, cells, or symbols. Objects have no Milestone 4 garbage collection,
and partially completed ordered commits may be visible until resume completes them.
