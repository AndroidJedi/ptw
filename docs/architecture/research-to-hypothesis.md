# Research to initial hypothesis

Research is evidence, not knowledge by itself. Commander preserves the stages:

```text
ResearchFinding (Source entities)
        |
        | derived_from
        v
Proposed Hypothesis + predeclared success criterion
        |
        v
Experiment -> Observation -> Insight -> Decision -> KnowledgeAssertion
```

`ResearchKnowledgeService` records each bounded finding as a permanent UUIDv7
`Source` with URI, publisher, publication date, concise finding summary, scoped
credibility, and optional external ID. A hypothesis may derive from multiple
sources; each source has its own relationship edge. The hypothesis remains
`proposed` and does not become accepted knowledge until tested and adopted by an
explicit decision.

Automated research is owned by explicit agents: `/research creative`,
`/research product`, `/research design`, and `/research engineering`. Each
records its `owner_agent`, `knowledge_domain`, and `research_type`, calls the
same provenance contract, stores concise findings, and separates source claims
from Commander interpretation.

PostgreSQL is the graph store:

- `commander_entities.id`: permanent UUID entity ID;
- `commander_entities.kind/attributes`: typed entity envelope and vertical
  attributes;
- `commander_relationships`: foreign-key-protected directed edges;
- `relation`: constrained predicate such as `derived_from`, `supports`,
  `contradicts`, or `supersedes`;
- audit entities: actor, concise reasoning summary, evidence IDs, and policy
  revision.

A dedicated graph database is unnecessary until measured query patterns exceed
recursive SQL/typed-edge capabilities. PostgreSQL remains the authoritative
store even if vector or graph projections are added later.

After ingestion, `/graph hypotheses` shows proposed hypotheses and the exact
Source UUIDs from which each was derived.

`/creative from <hypothesis-uuid>` validates that the selected hypothesis has
`research_type=creative_ideation`, then generates a creative linked to that
existing hypothesis. This preserves Source -> Hypothesis -> Creative lineage.

Product, design, and engineering hypotheses are consumed with
`/task from <hypothesis-uuid> <request>`. The platform retrieves the hypothesis
and permanent sources through the authenticated bridge, injects the bounded
evidence into the task specification, and appends a
`RESEARCH_CONTEXT_CONSUMED` event. Creative-owned hypotheses fail closed on
this path and must use `/creative from`.
