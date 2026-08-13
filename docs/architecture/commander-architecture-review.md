# PTW Commander architecture review

Status: canonical architecture baseline  
Reviewed repository: `AndroidJedi/ptw`, `main` at `bc1f5bd`  
Review date: 2026-08-13

## Executive decision

Build Commander as a modular orchestration service around an append-only
learning domain. Keep the existing Flutter Story system as the first creative
adapter. Do not put orchestration, experiment truth, or decision history in the
Flutter snapshot, template catalog, Telegram handlers, or a graph database.

The minimum scalable shape is a modular monolith with ports for creative
generation, publishing, metric ingestion, notifications, scheduling, object
storage, and persistence. PostgreSQL should be the transactional source of
runtime truth. Git remains the source for code, policies, and canonical
Markdown. Object storage holds immutable large assets. Embeddings are a later
retrieval projection, never authoritative knowledge.

This differs from the Bootstrap Addendum's “everything becomes graph entities”
wording. Relationships are first-class, but a dedicated graph database is not
justified. A relational entity/edge model plus typed lifecycle constraints is
simpler, transactional, auditable, and sufficient for the required questions.

## Repository findings

The repository is primarily an offline Flutter product prototype. It has:

- a local SharedPreferences JSON snapshot for projects, evidence, responses,
  Story drafts, shares, and generation events;
- a schema-driven Story editor and deterministic 1080x1920 renderer;
- a build-time MCP template catalog with validation and optimistic revision
  checks;
- three generations of creative code: legacy `features/share`, experimental
  `features/social_post_studio`, and the live `generated_share_editor` route;
- extensive Flutter tests and golden assets;
- no backend, Commander process, Telegram bot, production database client,
  deployment definition, scheduler, metrics ingestion, policy engine, or
  learning-domain persistence.

The repository fetched from GitHub is unrelated in Git history to the deployed
Python checkout at `/opt/ptw/platform`. That deployed tree must not be silently
merged into this repository. Reconciliation requires a separate provenance and
migration exercise.

## Documentation review

The two files under `docs/` were both current but served unrelated scopes.
Three additional Markdown sources at repository root carried product, design,
and point-in-time implementation context. No exported duplicates existed.

Weaknesses were discoverability, absent status labels, no context routes, and a
handoff whose schema-v2 narrative has already drifted from schema-v3 language
elsewhere. `docs/README.md` now declares authority and selective routes. Root
documents remain in place to preserve links; physical movement would add churn
without improving retrieval. The handoff is explicitly classified as a
snapshot, not architecture authority.

Future canonical documents should include compact metadata (status, owner,
topics, supersedes, reviewed revision). Commander can first retrieve from a
curated registry and lexical section index. Add embeddings only after measuring
misses; indiscriminate vector retrieval risks returning obsolete handoffs as
authority.

## Target boundaries

```text
Telegram / CLI / scheduler
          |
     command API
          |
 Commander application service ---- policy evaluator
          |
 generic learning domain
          |
 repository ports + outbox
     /         |          \
PostgreSQL  object store  adapters
                         /    |     \
                   creative publish metrics
                       (Instagram first)
```

Commander classifies a task, requests a minimal context bundle, invokes a
specialized workflow through a port, records outputs and relationships, applies
policy, and schedules the next command. It does not render images, call
Instagram APIs, calculate every analysis, or embed Telegram-specific concepts
in the domain.

## Domain model changes

The proposed list is a good vocabulary but needs refinement:

- `MetricSet` is a factual ingestion envelope; individual `MetricValue`s carry
  name, value, unit, attribution window, and source.
- `Observation` is a factual statement derived from a metric set, with its
  calculation method and evidence references.
- `Insight` is an interpretation of one or more observations.
- `Hypothesis` is a falsifiable claim with success criteria before an
  experiment starts.
- `Decision` is an explicit, versioned action or belief adoption. Replacement
  creates another decision and `supersedes` edges; it never updates history in
  place.
- `KnowledgeAssertion` represents the current usable rule while preserving its
  lineage to decisions and prior assertions.
- `CreativeComponent` is the generic aggregate member. `Hook`, `HeroImage`,
  `SupportingVisual`, `Caption`, and `CTA` are component kinds in the Instagram
  adapter, not tables baked into the generic core.
- `Artifact` describes immutable generated files and checksums. Entity records
  refer to artifacts rather than storing binary data.
- `AuditEvent` records command, actor, policy result, concise reasoning summary,
  evidence references, and resulting entity IDs. Hidden chain-of-thought is
  neither required nor stored.

Relationships use an explicit predicate vocabulary (`contains`, `derived_from`,
`tests`, `tested_in`, `measured_by`, `supports`, `contradicts`, `supersedes`,
`adopted_as`, `generated`) and may carry metadata. Database constraints prevent
dangling endpoints and duplicate edges.

## Stable IDs

Use UUIDv7 values internally and across APIs, Telegram payloads, database rows,
asset metadata, and future systems. UUIDv7 is globally unique, time sortable,
opaque, and does not require a central allocator. Human interfaces show a short
kind-prefixed display reference (for example `EXP-019D...`) derived from, but
never substituted for, the UUID. Never encode mutable meaning, database
sequence, campaign, or platform ID into the permanent identifier.

External IDs belong in a scoped alias table (`system`, `external_id`,
`entity_id`) with a uniqueness constraint. Asset object keys include the full
entity UUID and content digest.

## Lifecycle and invariants

The generic experiment state machine is draft -> approved -> running ->
completed -> evaluated. Cancelled is terminal. Only approved experiments can
start; only running experiments accept metric sets; only completed experiments
produce evaluation observations. A hypothesis and predeclared success criteria
must exist before approval.

The first demonstrated loop is:

1. Create falsifiable hypothesis and reusable components.
2. Compose a Creative and link it to the hypothesis.
3. Approve and run an Experiment under policy.
4. Ingest a MetricSet through the vertical adapter.
5. Complete the experiment and record an Observation.
6. Interpret it as an Insight.
7. append a Decision with confidence and evidence.
8. create a KnowledgeAssertion and schedule the next Task.

The demonstration uses supplied sample metrics. It proves state, lineage,
policy, persistence, and replay—not Instagram publishing or statistical
significance.

## Policies and autonomy

Policies are versioned configuration in Git and are snapshotted by digest on
each policy evaluation. Initial policy covers emergency stop, approval,
experiment concurrency, budget, confidence threshold, deployment permission,
rollback, and notification routing. Policy decides whether a command may
execute; it must not contain creative or vertical-specific business rules.

Important approvals create auditable commands with actor identity and expiry.
Telegram buttons should carry one-time command tokens rather than mutable
entity state. Emergency stop is deny-by-default, checked before dispatch and
before each external side effect.

## Telegram

Telegram is the primary human control plane, not the source of truth. A thin
adapter should authenticate an allowlist of Telegram user/chat IDs, translate
commands and callbacks into application commands, and render read models for:
task submission, status, queue, reasoning summaries, experiment progress,
approvals, deployment, policy inspection, and emergency stop.

Long operations return a task ID immediately. An outbox worker sends updates
idempotently. Callback tokens expire and are single-use. Every mutating command
is authorized again server-side. The architecture should retain a CLI/admin
adapter for recovery if Telegram is unavailable.

## Storage allocation

### PostgreSQL now

Store entities, relationships, experiment lifecycle, metric values, decisions,
knowledge assertions, tasks, policy evaluations, audit events, aliases, and an
outbox. JSONB is appropriate for evolving vertical attributes, but searchable
identity, lifecycle, and lineage remain relational columns and edges.

### Git now

Store code, migrations, policy defaults, canonical Markdown, prompt/workflow
definitions, and declarative creative catalogs. Runtime decisions do not go to
Git because concurrent agents and mutable operational state need transactions.

### Object storage when assets leave one host

Store generated images/video and source media immutably with checksums and
metadata. The prototype can use a local filesystem adapter first. Do not store
large media in PostgreSQL or commit generated campaign assets to Git.

### Embeddings later

Use PostgreSQL full-text/metadata retrieval first. An embedding index may be a
rebuildable projection over approved documentation and knowledge assertions.
It must retain authority, revision, and entity filters and never replace the
relationship store.

## Deployment review

This GitHub tree now includes an isolated Commander Compose deployment. The VPS
also contains a separate,
unrelated-history Commander-style Python deployment and a `/root/ptw-stage`
copy. Treat both as operational evidence, not code to absorb implicitly.

The target service should eventually have separate API/worker processes from
one codebase, PostgreSQL, durable object storage, migrations run as a release
step, health/readiness endpoints, structured logs, backups, and an outbox-based
worker. Start as a modular monolith; microservices would multiply failure and
deployment modes before workload boundaries are known.

## Risks

1. Documentation drift could make obsolete handoffs look authoritative.
2. Current generated creative IDs are deterministic labels, not globally
   stable entity IDs.
3. SharedPreferences is a whole-snapshot prototype store with no concurrency,
   referential integrity, audit log, or server durability.
4. Three generator paths invite accidental reuse of inactive code.
5. Metrics can be misattributed without platform ID aliases and attribution
   windows.
6. Autonomous publication or spend without idempotency and policy snapshots can
   duplicate irreversible side effects.
7. “Knowledge graph” can become an untyped property bag unless lifecycle and
   relationship predicates are constrained.
8. Conclusions from tiny Instagram samples can be mistaken for general rules;
   confidence and scope must remain explicit.
9. Telegram compromise would expose operational control unless authorization,
   token expiry, and emergency-stop checks are server-side.
10. The unrelated VPS/GitHub histories create migration and ownership risk.

## Migration strategy

1. Land the generic domain, repository port, policy gate, SQL schema, and local
   demonstration without changing the Flutter runtime.
2. Implement PostgreSQL repositories and outbox; import no prototype data until
   mapping and provenance are defined.
3. Wrap the live generated Story pipeline behind a creative adapter. Deprecate
   older generators only after call-site and golden-test migration.
4. Add authenticated Telegram command/status/approval flows over the application
   API.
5. Add manual publishing and metric ingestion adapters first; automate only
   after idempotency, attribution, and rollback behavior are proven.
6. Reconcile the VPS deployment as a separate audited migration, then deploy the
   modular service alongside—not inside—the Flutter client.
7. Measure context-routing misses before adding full-text automation or vectors.

## Intentionally deferred

Instagram publishing, automated spend, statistical engines, cloud object
storage, embeddings, distributed scheduling, production backup automation,
and cleanup of legacy Flutter generators remain deferred. Telegram webhook and
delivery adapters now exist, but public activation remains owner-controlled and
requires private credentials plus a DNS-backed HTTPS endpoint.
