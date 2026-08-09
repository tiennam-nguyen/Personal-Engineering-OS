# ADR 0014: Immutable cross-workflow links and derived graph

Status: Accepted

## Context

Historical source artifacts cannot safely be rewritten merely to add graph edges because prior
runs freeze exact revisions. Milestone 7 also requires navigation from both endpoints without
making SQLite canonical.

## Options

1. Rewrite source artifacts to append outgoing links.
2. Make a relation artifact or SQLite row the canonical edge.
3. Preserve outgoing links and permit a strict incoming link hosted by a newly created target.
4. Store two inverse canonical edges.

## Decision

Use option 3. Legacy `{rel,target}` links remain unchanged. A new target may host
`{source,rel}`, meaning `source --rel--> host`. One logical `(source, relation, target)` edge has
exactly one canonical host. SQLite materializes adjacency and backlinks with the host ID and exact
host revision. Reversible means querying the same directed edge from either endpoint; no inverse
relation is persisted.

## Consequences

Old artifacts remain byte-stable and claim-to-ADR support has the correct direction without source
mutation. The link parser is a strict union and graph reads must verify every projected row against
its canonical host. Generic editing, unlinking, and artifact revision machinery remain deferred.

## What would change this decision

A verified immutable artifact-revision store could make source-hosted relation revision safe
without invalidating historical run verification.
