# ADR 0015: Canonical evaluation reports authorize exact routes

Status: Accepted

## Context

Model-assisted production workflows need evidence that a specific route passed a frozen policy.
Candidate calls can be interrupted, SQLite is disposable, and changing a suite, protocol, or output
contract must invalidate old evidence without rewriting history.

## Decision

Evaluation is the fixed `system.evaluate-model-route@1.0.0` workflow. It freezes suite cases,
protocol bytes, route identity, scorer versions, thresholds, and budgets before making calls. Calls
bypass cache. A completed response audit is reused on resume; a journal containing
`model.call_started` without a validated response is an unknown outcome and is never retried.

The canonical `system.eval_report` and its succeeded source run authorize only the exact tuple of
task, route fingerprint, suite fingerprint, protocol hash, and output-schema hash. Qualification
selects the latest valid report by deterministic artifact chronology. SQLite is only a projection.

Production goldens and thresholds are static reviewed YAML under `evals/`; candidate responses do
not generate either.

## Consequences

Policy or contract changes fail closed until a new evaluation succeeds. A FAILED report revokes an
older QUALIFIED report for the same identity. Recovery may continue unexecuted cases but cannot
guess whether an interrupted external call completed. Real-provider judging, retries, statistical
quality claims, pricing, and cross-suite rankings remain outside Milestone 8.

## What would change this decision

A provider-supported idempotency and result-retrieval contract could make unknown outcomes safely
recoverable without repeating a candidate call.
