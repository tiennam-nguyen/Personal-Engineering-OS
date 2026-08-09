# ADR 0013: Deterministic learning evidence aggregate

Status: Accepted

## Context

Milestone 6 must turn an observable capability goal, a prerequisite diagnostic, and an exercise
attempt into durable learning evidence without model judgment, scalar mastery, or artifact-schema
sprawl. Resume must use frozen inputs and SQLite must remain a rebuildable projection.

## Options

1. Use a model to grade and generate a separate artifact for every concept, gap, plan, and score.
2. Store mutable learning state in SQLite and recompute it during resume.
3. Use deterministic exact verifiers and three canonical aggregate artifacts: `learning.goal`,
   `learning.attempt`, and `learning.mastery`.

## Decision

Use option 3. `learning.goal` aggregates the validated goal, acyclic prerequisite graph,
diagnostic evidence, ordered gaps, plan, first exercise, and future practice events. An attempt is
bound to an exact goal revision and planned exercise. Mastery records recall, explanation,
application, transfer, and retention separately; a same-session attempt leaves retention
`NOT_ASSESSED`. Review dates follow the named `fixed_interval/v1` policy and are recommendations,
not epistemic truth.

## Consequences

Runs are reproducible from frozen JSON bytes, independent verification can recompute every
decision, and canonical artifacts survive projection loss. Exact-text and single-choice grading
are deliberately narrow. There is no overall score, mastered boolean, model route, model cache,
or hidden semantic judgment.

## What would change this decision

Evidence that another exercise verifier has deterministic semantics and an independently testable
lifecycle may add it. Longitudinal observations may introduce a later retention policy, but must
not rewrite historical attempt or mastery artifacts.
