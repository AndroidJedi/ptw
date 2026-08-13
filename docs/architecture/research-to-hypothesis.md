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

The first automated adapter is deliberately scoped to `creative_ideation` and
is exposed as `/research creative <topic>`. It searches through a configured provider,
calls this ingestion contract, preserves exact provenance, stores only concise
findings, and separates source claims from Commander interpretation. Other
research kinds require separate typed workflows rather than overloading this
command.

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
