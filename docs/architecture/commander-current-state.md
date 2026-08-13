# Commander current state

Status: active implementation handoff  
Updated: 2026-08-13  
Architecture authority: [`commander-architecture-review.md`](commander-architecture-review.md)

## Completed milestone

The first generic learning-loop foundation is implemented in `commander/`.
It includes UUIDv7 IDs, append-only entities and relationships, explicit
experiment-state events, versioned policy gates, audit summaries, a selective
context broker, a replayable local JSONL adapter, and an Instagram creative
adapter.

`python3 -m commander.demo` demonstrates:

Hypothesis -> Creative -> Experiment -> MetricSet -> Observation -> Insight ->
Decision -> KnowledgeAssertion -> Next Task.

The PostgreSQL target schema begins at
`db/migrations/001_commander_foundation.sql`. It is not wired to the Python
repository yet. Telegram and Instagram network integrations do not exist.

## Last verification

From the repository root:

```text
python3 -m unittest discover -s tests/commander -v  # 8 passed
python3 -m commander.demo --output-dir .local/commander-demo  # passed
python3 -m compileall -q commander tests/commander  # passed
git diff --check  # passed
```

Dart and Flutter were unavailable on the VPS, so Flutter tests were not run.

## Next milestone

Implement a PostgreSQL `KnowledgeStore` adapter and transactional outbox, then
add a minimal authenticated Telegram adapter for status, experiment approval,
policy inspection, and emergency stop. Keep the transport thin and make all
authorization and policy decisions inside the application boundary.

## Operational warning

The GitHub repository and the existing `/opt/ptw/platform` deployment have
unrelated Git histories. Never merge or overwrite one with the other without a
separate migration and provenance review.
