# Business Idea Evolution System — Clean VPS Bootstrap Specification

**Status:** FINAL v1 specification  
**Authoritative folder:** `ideaGeneration/`  
**Runtime:** existing VPS  
**Control plane:** existing Telegram bot  
**Persistence:** existing PostgreSQL service, clean application schema  
**Evolution core:** `GENERATE → EVALUATE → EVOLVE`

This document supersedes older experimental idea-generation/knowledge-graph/agent architecture for this system.

---

## 1. Goal

Build the smallest reliable self-evolving business-idea system that can repeatedly:

1. generate a population of 10 ideas;
2. evaluate all 10 through 10 different reasoning contexts;
3. preserve all historical ideas/evaluations;
4. use the latest generation + historical winners + current failures to create the next generation;
5. allow the owner to intervene completely through Telegram;
6. recover automatically from ordinary execution failures;
7. produce reports proving whether generations are actually improving.

Do **not** turn this into a multi-agent platform.

One LLM execution layer is enough. "Contexts" are prompts/lenses, not separate long-running agents.

---

## 2. Existing infrastructure and clean rebuild

The VPS is already provisioned. Git, Telegram, PostgreSQL, deployment access, and secrets already exist.

### 2.1 Preserve

Preserve/reuse when healthy:

- VPS;
- repository and Git remote;
- SSH/deploy access;
- existing Telegram bot token and bot identity;
- authorized owner Telegram chat IDs;
- PostgreSQL service/container;
- database credentials when appropriate;
- Docker/Compose installation;
- unrelated VPS services;
- working secrets/env values.

Never print or commit secrets.

### 2.2 Inspect before deleting

Before destructive work:

```text
git status
git pull --ff-only
```

Then inspect:

- repository structure;
- running Docker/systemd/process-manager services;
- old app processes/workers/schedulers;
- current Telegram poller;
- PostgreSQL database/schema/tables;
- environment/secrets;
- shared/unrelated services.

### 2.3 Back up and remove old application state

The previous idea-system implementation is disposable.

Before resetting DB:

1. identify the exact DB/schema belonging to this application;
2. verify unrelated systems do not share it;
3. make a one-time SQL dump outside Git;
4. stop old app/background workers;
5. stop the old Telegram poller;
6. remove obsolete old idea-system code/migrations/jobs/services;
7. clear old app tables/schema;
8. apply only this v1 schema.

If the app owns the whole DB:

```sql
DROP SCHEMA IF EXISTS public CASCADE;
CREATE SCHEMA public;
```

If DB is shared, drop only enumerated app-owned objects.

### 2.4 Telegram migration safety

Reuse the existing bot.

There must be **exactly one poller** for its token.

During migration:

```text
old app stopped
old Telegram poller stopped
Postgres stays available
new app deployed
new Telegram poller started once
```

Do not create a new bot unless the current token is genuinely unusable.

---

## 3. Deliberate v1 simplicity

### Build

- PostgreSQL history.
- 10 fixed-at-any-moment reasoning contexts.
- Context owner editing/version history.
- 10 ideas per generation.
- 10 evaluator-context passes per generation.
- Hall of Fame = historical top 3.
- Failures = current bottom 2.
- Default generated mix ≈ 70% exploit / 30% explore.
- Owner idea injection.
- Telegram control.
- Reports.
- Bounded automatic recovery.
- Optional autopilot.

### Do not build

- embeddings;
- vector DB;
- clustering;
- semantic idea classes;
- knowledge graph;
- mutation operator database;
- autonomous context evolution;
- Redis/Celery/Kafka/Kubernetes;
- separate long-lived agents;
- autonomous production source-code rewriting;
- full-history prompts on every cycle.

The evolving object is the **idea population**.

---

## 4. Mission and contexts

Mission source:

`ideaGeneration/docs/TASK_450M_5Y.md`

Initial context sources:

`ideaGeneration/docs/contexts/*.md`

Stable context codes:

```text
C01 ... C10
```

The Markdown files seed PostgreSQL. Runtime reads contexts from PostgreSQL.

Owner context edits are allowed. Autonomous context evolution is not.

---

## 5. Evolution algorithm

### 5.1 Generation 1

Normally:

```text
TASK + C01 -> 1 idea
...
TASK + C10 -> 1 idea
```

If owner ideas are pending before G1, reserve those slots first and generate only remaining slots.

Total generation size is always 10.

### 5.2 Evaluation

Each of 10 active contexts evaluates the **entire batch of 10 ideas in one LLM call**.

Therefore:

```text
10 evaluator calls
100 evaluation rows
```

Each idea aggregate score = mean of its 10 context scores.

### 5.3 Generation 2+

EVOLVE receives only a small working set:

```text
ORIGINAL TASK
ACTIVE OWNER GUIDANCE
ALL 10 CURRENT IDEAS + aggregate scores + compact critique
HALL OF FAME: top 3 from earlier completed generations
FAILURES: bottom 2 from current generation + failure critique
```

Do not include the whole historical archive.

### 5.4 Hall of Fame

Derived query; no dedicated table required.

Default = top 3 ideas by aggregate score from completed generations before the current generation.

Purpose: prevent losing a historically strong branch after a weak generation.

### 5.5 Failures

Bottom 2 from current generation.

They are warnings/repair opportunities, not privileged parents.

### 5.6 Exploit / explore

Without human injections:

```text
7 exploit
3 explore
```

With human injections, human ideas take slots first.

For remaining model slots, use approximately 70/30 split.

Example:

```text
2 owner ideas
6 exploit
2 explore
= 10
```

Exploit normally references one or more parent IDs.

Explore may use no parents.

Rotate which contexts produce explore candidates so the same context is not permanently assigned.

---

## 6. Owner idea injection

The owner can submit an idea at any time.

Command:

```text
/idea_add TEXT
```

Rules:

- store submission immediately;
- do not modify an already completed generation;
- guarantee the submission a slot in the **next generation with capacity**;
- owner submissions fill slots oldest-first;
- they displace model-generated candidates, not historical ideas;
- normalize formatting if needed, but do not change the business concept;
- after insertion, evaluate them exactly like all other candidates;
- no scoring advantage;
- if >10 owner ideas are pending, overflow waits for following generations.

Owner idea mode:

```text
human
```

Once inserted into a generation, it is immutable history.

---

## 7. PostgreSQL schema

Use SQL migrations.

### 7.1 missions

```sql
CREATE TABLE missions (
    id BIGSERIAL PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    task_text TEXT NOT NULL,

    status TEXT NOT NULL DEFAULT 'active'
      CHECK (status IN ('active','paused','completed')),

    generation_size INTEGER NOT NULL DEFAULT 10,
    hall_of_fame_size INTEGER NOT NULL DEFAULT 3,
    failure_size INTEGER NOT NULL DEFAULT 2,
    exploit_count INTEGER NOT NULL DEFAULT 7,
    explore_count INTEGER NOT NULL DEFAULT 3,

    auto_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    cadence_hours INTEGER NOT NULL DEFAULT 24,
    max_generations_per_day INTEGER NOT NULL DEFAULT 1,

    run_series_remaining INTEGER NOT NULL DEFAULT 0,
    stop_after_current_cycle BOOLEAN NOT NULL DEFAULT FALSE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 7.2 contexts

```sql
CREATE TABLE contexts (
    id BIGSERIAL PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    prompt_text TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order INTEGER NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 7.3 context_revisions

```sql
CREATE TABLE context_revisions (
    id BIGSERIAL PRIMARY KEY,
    context_id BIGINT NOT NULL REFERENCES contexts(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    name TEXT NOT NULL,
    prompt_text TEXT NOT NULL,
    changed_by TEXT NOT NULL DEFAULT 'owner',
    change_note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(context_id, version)
);
```

Every owner edit creates immutable revision history.

### 7.4 generations

```sql
CREATE TABLE generations (
    id BIGSERIAL PRIMARY KEY,
    mission_id BIGINT NOT NULL REFERENCES missions(id) ON DELETE CASCADE,
    number INTEGER NOT NULL,
    status TEXT NOT NULL
      CHECK (status IN ('creating','created','evaluating','completed','failed')),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    error_text TEXT,
    UNIQUE(mission_id, number)
);
```

### 7.5 ideas

```sql
CREATE TABLE ideas (
    id BIGSERIAL PRIMARY KEY,
    mission_id BIGINT NOT NULL REFERENCES missions(id) ON DELETE CASCADE,
    generation_id BIGINT NOT NULL REFERENCES generations(id) ON DELETE CASCADE,
    creator_context_id BIGINT REFERENCES contexts(id),

    mode TEXT NOT NULL
      CHECK (mode IN ('initial','exploit','explore','human')),

    title TEXT NOT NULL,
    one_liner TEXT NOT NULL,
    details JSONB NOT NULL,

    parent_ids BIGINT[] NOT NULL DEFAULT '{}',
    lineage_note TEXT,

    owner_submission_id BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_ideas_generation ON ideas(mission_id, generation_id);
CREATE INDEX idx_ideas_parent_ids ON ideas USING GIN(parent_ids);
```

Expected `details`:

```json
{
  "customer": "...",
  "problem": "...",
  "product": "...",
  "business_model": "...",
  "distribution": "...",
  "automation": "...",
  "five_year_exit_logic": "...",
  "key_risks": ["..."],
  "first_validation_test": "..."
}
```

### 7.6 idea_evaluations

```sql
CREATE TABLE idea_evaluations (
    id BIGSERIAL PRIMARY KEY,
    idea_id BIGINT NOT NULL REFERENCES ideas(id) ON DELETE CASCADE,
    evaluator_context_id BIGINT NOT NULL REFERENCES contexts(id),

    score NUMERIC(5,2) NOT NULL CHECK (score >= 0 AND score <= 100),
    criteria JSONB NOT NULL,
    strengths TEXT NOT NULL,
    critique TEXT NOT NULL,
    fatal_flaw TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(idea_id, evaluator_context_id)
);
```

### 7.7 aggregate view

```sql
CREATE VIEW idea_scores AS
SELECT
    i.id AS idea_id,
    i.mission_id,
    i.generation_id,
    AVG(e.score)::NUMERIC(5,2) AS aggregate_score,
    COUNT(e.id) AS evaluation_count
FROM ideas i
JOIN idea_evaluations e ON e.idea_id = i.id
GROUP BY i.id, i.mission_id, i.generation_id;
```

### 7.8 guidance

```sql
CREATE TABLE guidance (
    id BIGSERIAL PRIMARY KEY,
    mission_id BIGINT NOT NULL REFERENCES missions(id) ON DELETE CASCADE,
    idea_id BIGINT REFERENCES ideas(id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 7.9 idea_submissions

```sql
CREATE TABLE idea_submissions (
    id BIGSERIAL PRIMARY KEY,
    mission_id BIGINT NOT NULL REFERENCES missions(id) ON DELETE CASCADE,
    title TEXT,
    raw_text TEXT NOT NULL,

    status TEXT NOT NULL DEFAULT 'pending'
      CHECK (status IN ('pending','scheduled','inserted','cancelled')),

    target_generation_number INTEGER,
    inserted_idea_id BIGINT REFERENCES ideas(id) ON DELETE SET NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 7.10 executions

```sql
CREATE TABLE executions (
    id BIGSERIAL PRIMARY KEY,
    mission_id BIGINT NOT NULL REFERENCES missions(id) ON DELETE CASCADE,
    generation_id BIGINT REFERENCES generations(id) ON DELETE SET NULL,

    phase TEXT NOT NULL
      CHECK (phase IN ('generate','evaluate','evolve','normalize_human','telegram_chat')),

    status TEXT NOT NULL
      CHECK (status IN ('running','succeeded','failed')),

    context_id BIGINT REFERENCES contexts(id),
    attempt INTEGER NOT NULL DEFAULT 1,
    model_name TEXT,
    prompt_hash TEXT,

    input_tokens BIGINT,
    output_tokens BIGINT,

    request_json JSONB,
    response_json JSONB,
    error_text TEXT,

    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);
```

Never store secrets in request/response audit.

### 7.11 reports

```sql
CREATE TABLE reports (
    id BIGSERIAL PRIMARY KEY,
    mission_id BIGINT NOT NULL REFERENCES missions(id) ON DELETE CASCADE,
    generation_id BIGINT REFERENCES generations(id) ON DELETE SET NULL,

    report_type TEXT NOT NULL
      CHECK (report_type IN ('generation','run_series','recovery')),

    title TEXT NOT NULL,
    body_text TEXT NOT NULL,
    payload JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 7.12 telegram_events

```sql
CREATE TABLE telegram_events (
    id BIGSERIAL PRIMARY KEY,
    chat_id BIGINT NOT NULL,
    direction TEXT NOT NULL CHECK (direction IN ('in','out')),
    event_type TEXT NOT NULL,
    text TEXT,
    payload JSONB,
    execution_id BIGINT REFERENCES executions(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

## 8. Prompt contracts

Use structured JSON output and schema validation for any model output that changes DB state.

### 8.1 GENERATE

Input:

```json
{
  "task": "...",
  "context": {"code":"C01","name":"...","prompt":"..."},
  "owner_guidance": []
}
```

Return exactly one idea object with required fields.

Generation 1 mode = `initial`.

### 8.2 EVALUATE

Each evaluator receives all 10 ideas.

Return exactly one evaluation per idea ID.

Use the 100-point rubric defined in `TASK_450M_5Y.md`.

Validate:

- exactly all 10 IDs;
- no duplicate IDs;
- no unknown IDs;
- score 0..100;
- criteria consistent with rubric.

### 8.3 Compact critique

Do not add a summarizer model call.

For each idea pass to EVOLVE:

- aggregate score;
- critique from evaluator closest to median score;
- critique from most critical evaluator.

### 8.4 EVOLVE

Input:

```json
{
  "task": "...",
  "context": {...},
  "mode": "exploit|explore",
  "current_generation": [...],
  "hall_of_fame": [...],
  "failures": [...],
  "owner_guidance": [...]
}
```

Exploit:

- materially improve/combine/reposition/simplify;
- normally reference parent IDs.

Explore:

- substantially different attack on original mission;
- may use `parent_ids=[]`.

Cosmetic rewrites are not new ideas.

---

## 9. Cycle semantics

### 9.1 `/run`

`/run` means exactly:

```text
create one next generation
evaluate it completely
persist report
notify owner
STOP
```

It never launches another generation by itself.

### 9.2 `/run N`

Run N generations sequentially.

After each generation:

1. persist generation report;
2. send Telegram summary;
3. process any new owner guidance/context edits queued since previous generation;
4. check `/stop` and pause state;
5. start next only if allowed.

Persist the remaining count in PostgreSQL.

### 9.3 `/stop`

Graceful stop after the current generation reaches a safe boundary.

Do not kill a DB transaction/model request mid-flight.

Preserve `run_series_remaining`.

### 9.4 `/continue`

Resume preserved `/run N` sequence from the next required generation.

Never restart already completed generations.

### 9.5 `/pause`

Pause mission and turn off automatic progression.

### 9.6 `/resume`

Resume mission. Does not automatically enable autopilot.

---

## 10. Creating a generation with human submissions

At generation start:

1. acquire mission advisory/row lock;
2. determine next generation number;
3. reserve pending owner submissions oldest-first;
4. mark them `scheduled`;
5. normalize each to the standard idea format if needed;
6. insert them as `mode='human'`;
7. calculate remaining slots;
8. create model ideas for remaining slots only;
9. ensure total ideas = 10;
10. evaluate all 10 identically;
11. on successful completion mark submissions `inserted`;
12. release lock.

If generation fails before safe completion, reconciliation must not lose or duplicate submissions.

---

## 11. Telegram — required commands

Full reference also exists in `TELEGRAM_CONTROL.md`.

### System

```text
/status
/run
/run N
/stop
/continue
/pause
/resume
/autopilot on
/autopilot off
/autopilot 24h
```

### Rankings/history

```text
/ranking
/generation N
/idea ID
/top [N]
/history [N]
/lineage ID
```

### Reports

```text
/report
/report G7
/reports [N]
```

### Owner ideas

```text
/idea_add TEXT
/idea_queue
/idea_cancel SUBMISSION_ID
```

### Feedback

```text
/guidance TEXT
/guidance_list
/guidance_clear ID
/feedback IDEA_ID TEXT
/keep IDEA_ID [TEXT]
/reject IDEA_ID [REASON]
```

### Contexts

```text
/contexts
/context C03
/context_set C03 TEXT
/context_name C03 NAME
/context_history C03
/context_restore C03 VERSION
/context_enable C03
/context_disable C03
```

### Audit

```text
/executions [N]
/errors [N]
/cost
/task
/help
```

---

## 12. Telegram behavior details

### `/status`

Must show live progress, not only last completed state:

```text
Mission: ACTIVE
Autopilot: OFF
Running: YES
Generation: G7
Phase: EVALUATE
Progress: 6/10 evaluator contexts

Latest completed: G6
Total ideas stored: 68
Pending owner ideas: 2

Current leader: #61 — 87.4
Historical leader: #42 — 91.2

Run-series remaining: 4
Last error: none
```

### `/ranking`

All 10 latest completed ideas, score descending, including mode.

### `/top 25`

Best 25 ideas across all completed generations.

### `/history`

For each generation:

```text
G1 best / avg / worst
G2 best / avg / worst
...
```

Purpose: visibly test whether evolution improves.

### `/lineage`

Render ancestry recursively from `parent_ids`; no graph DB.

### Context edits

`/context_set C03 TEXT`:

1. save revision;
2. increment version;
3. update current prompt;
4. apply only to future calls;
5. notify owner.

`/context_restore C03 2` creates a **new** version containing old v2 text.

Do not rewrite history.

A run requires exactly 10 active contexts.

### Free-form Telegram

Support Russian/Ukrainian/English convenience intents, e.g.:

```text
"покажи рейтинг"
"что сейчас выполняется?"
"добавь мою идею: ..."
"покажи контекст C04"
"измени C04: ..."
```

LLM may classify ambiguous chat into a structured supported action, but app code validates/executes it.

---

## 13. Reporting

Persist a deterministic report after every completed generation.

Generation report minimum:

- generation number/time;
- ranked top 10;
- best score;
- average score;
- worst score;
- delta versus previous generation;
- historical best;
- Hall of Fame changes;
- owner-submitted candidates and scores;
- bottom two + failure reasons;
- notable evaluator disagreement;
- top idea lineage;
- active guidance affecting the generation;
- recovery incidents;
- model call/token summary.

Telegram compact summary:

```text
✅ G7 complete

Best: #73 — 89.1
Previous best: 86.2
Δ best: +2.9
Average: 72.8
Historical best: #73 — 89.1

Owner ideas: 1
Recoveries: 1
Total ideas: 70

/report G7
```

For `/run N`, create a final run-series report:

- requested generations;
- completed generations;
- why series ended;
- start best score;
- end best score;
- best discovered idea;
- generation trend;
- recovery incidents.

---

## 14. Self-healing recovery

### 14.1 Rule

For the same failing step:

```text
failure
→ automatic recovery attempt 1
→ if still failing: automatic recovery attempt 2
→ if recovered: continue automatically
→ if both fail: stop automatic progression safely
```

Maximum automatic recovery attempts: **2**.

Never infinite retry.

### 14.2 Recoverable examples

- LLM timeout/network error;
- rate limit;
- malformed structured output;
- missing/duplicate evaluator entry;
- invalid parent IDs from model output;
- temporary PostgreSQL connection failure;
- Telegram send failure;
- restart during generation/evaluation;
- stale execution row;
- incomplete but safely resumable evaluator batch.

### 14.3 Safe recovery actions

May:

- retry with bounded backoff;
- issue structured-output repair prompt;
- reconnect DB;
- retry Telegram send;
- reload persisted state;
- resume only missing evaluator calls;
- reconcile incomplete execution records;
- normalize recoverable model output;
- restart an internal in-process task;
- verify idempotent migrations/state.

Must not:

- delete completed generations;
- rewrite old scores;
- drop DB;
- change secrets;
- edit mission/contexts;
- silently skip evaluators;
- fabricate results;
- autonomously rewrite production source code.

### 14.4 Telegram recovery reporting

Attempt 1:

```text
🟡 Recoverable error
G7 / EVALUATE / C04
Cause: malformed structured output

Recovery 1/2:
requesting corrected structured response
```

Success:

```text
🟢 Recovery succeeded
G7 / EVALUATE / C04
Attempt 1/2

Execution continues automatically.
```

Attempt 2:

```text
🟠 Recovery attempt 1 failed
Trying 2/2 automatically.
```

Terminal:

```text
🔴 Automatic recovery failed
G7 / EVALUATE / C04
Attempts: 2/2

Automatic progression stopped safely.
Completed data preserved.
Run-series remaining: 4

/status
/errors
```

### 14.5 Recovery in `/run N`

If either attempt succeeds, continue current generation and series automatically.

If both fail:

- do not create next generation;
- preserve remaining count;
- keep partial state for reconciliation;
- notify owner;
- block `/continue` until health/reconciliation is valid.

### 14.6 Restart recovery

On application startup:

1. inspect `creating` / `evaluating` generations;
2. inspect `running` executions;
3. detect already persisted work;
4. resume only missing idempotent work;
5. do not duplicate ideas/evaluations/submissions;
6. after two failed reconciliation attempts, stop and notify owner.

### 14.7 Important boundary

The runtime can self-heal **execution state**.

It does not self-modify application source code.

If the failure is a real code defect, record diagnosis and stop after two safe attempts. Codex CLI can then be used as the maintenance/deployment tool.

---

## 15. Concurrency and idempotency

Use PostgreSQL advisory lock or equivalent mission row lock.

Protect:

- unique `(mission_id, generation.number)`;
- unique `(idea_id, evaluator_context_id)`;
- stable submission state transitions;
- exactly one active cycle per mission;
- exactly one Telegram poller.

`/run` while running returns live `/status` information and does nothing else.

---

## 16. Autopilot

Default after bootstrap:

```text
OFF
```

Default cadence:

```text
24h
max_generations_per_day = 1
```

Autopilot runs one complete generation per scheduled event.

It uses the same recovery rules.

Repeated terminal failure disables further progression and notifies owner.

User-facing timestamps: `Europe/Kyiv`.

---

## 17. LLM provider

Keep provider behind a small interface such as:

```python
async def generate_structured(
    mode: str,
    system_prompt: str,
    input_payload: dict,
    output_schema: dict,
) -> dict:
    ...
```

Provider/model are config, not business logic.

Use official current SDK for configured provider.

Validate structured outputs before DB writes.

Do not live-call the model during deployment tests unless explicitly enabled.

---

## 18. Telegram access control

Use allowed chat IDs from existing config/env.

Unauthorized chats:

- cannot read mission;
- cannot mutate state;
- cannot receive sensitive data.

All state-changing owner actions should be logged in `telegram_events`.

---

## 19. Deployment shape

Keep runtime minimal:

```text
Telegram
   |
Python app
   |-- Telegram control
   |-- scheduler/run-series controller
   |-- evolution engine
   |-- recovery controller
   |-- reporting
   |-- LLM adapter
   |
PostgreSQL
```

Docker Compose is preferred if current deployment already uses it.

No public web port is required for Telegram long polling.

Do not package Codex CLI into production runtime.

---

## 20. Environment

Example only:

```text
APP_ENV=production
TZ=Europe/Kyiv

DATABASE_URL=...

TELEGRAM_BOT_TOKEN=...
TELEGRAM_ALLOWED_CHAT_IDS=...

LLM_PROVIDER=openai
LLM_MODEL=...
OPENAI_API_KEY=...

AUTOPILOT_DEFAULT_ENABLED=false
AUTOPILOT_DEFAULT_CADENCE_HOURS=24
MAX_GENERATIONS_PER_DAY=1

LOG_LEVEL=INFO
```

Reuse existing secrets where healthy.

Never commit real `.env`.

---

## 21. Clean-bootstrap procedure

### Phase A — inspect

1. `git status`
2. `git pull --ff-only`
3. inventory services/processes/schema/env/Telegram.
4. distinguish shared infrastructure from old app.

### Phase B — protect

1. preserve secrets/token/chat IDs;
2. make one-time old DB backup outside Git;
3. record backup path.

### Phase C — stop old runtime

1. old app;
2. old workers/schedulers;
3. old Telegram poller.

Postgres remains up.

### Phase D — clean

1. remove obsolete old app logic;
2. reset only app-owned DB objects;
3. verify no legacy active tables/services remain.

### Phase E — install

1. add new code/migrations/tests;
2. migrate schema;
3. seed mission exactly once;
4. seed C01...C10 exactly once;
5. start exactly one bot/app;
6. verify DB and Telegram.

### Phase F — dry validation

Use mocked LLM provider.

Verify:

```text
/status
/help
/task
/contexts
/top
/report
```

Verify:

- `/run` mock creates exactly one generation;
- `/run 3` supports series;
- `/stop` and `/continue`;
- human idea queue;
- context versioning;
- recovery attempt 1 success;
- recovery attempt 2 success;
- two-attempt terminal stop;
- restart reconciliation;
- no duplicate rows.

Reset mock-generated data after tests so live generation count is 0.

### Phase G — handoff

Autopilot must remain OFF.

Do not run G1 automatically.

Send:

```text
🟢 Clean v1 deployment ready

Old implementation: removed
Old DB: backed up and cleared
Postgres: OK
Telegram: OK
Contexts: 10/10
Mission: loaded
Tests: PASS
Autopilot: OFF
Generations: 0

/start: /run
multi-generation: /run N
status: /status
```

---

## 22. Required tests

At minimum:

### Database

- idempotent mission seed;
- idempotent context seed;
- context revision history;
- generation uniqueness;
- evaluation uniqueness;
- aggregate score;
- Hall of Fame excludes current/incomplete;
- failure bottom N;
- submissions state transitions;
- reports survive restart.

### Evolution

- 10 total slots;
- human ideas consume slots first;
- remaining model split approximately 70/30;
- all 10 evaluated by all 10 contexts;
- invalid parent IDs rejected/repaired;
- entire archive not placed into EVOLVE prompt.

### Telegram

- unauthorized chat blocked;
- `/status` shows active phase/progress;
- `/ranking`, `/top`, `/history`, `/lineage`;
- `/idea_add`, queue/cancel;
- `/context_set/history/restore`;
- `/run` exactly one;
- `/run N`;
- `/stop`;
- `/continue`;
- `/report`;
- guidance/feedback/keep/reject.

### Recovery

Simulate:

- timeout recovered attempt 1;
- malformed JSON recovered attempt 2;
- both attempts fail;
- DB reconnect;
- restart during creating;
- restart during evaluating;
- partial evaluator batch.

Assert:

- max 2 attempts;
- successful recovery continues automatically;
- terminal recovery stops next generation;
- remaining run-series count persists;
- no duplicates;
- owner notification generated.

---

## 23. Acceptance criteria

Implementation is ready only when:

1. old idea-system runtime is stopped/removed;
2. old application DB is backed up once and active old schema cleared;
3. shared VPS infrastructure is intact;
4. exactly one Telegram poller runs;
5. mission exists once;
6. exactly 10 active contexts exist;
7. context revisions work;
8. `/run` produces exactly one generation and stops;
9. G1 contains exactly 10 ideas and 100 evaluations when successful;
10. `/run N`, `/stop`, `/continue` persist correctly;
11. all old ideas remain historical after future generations;
12. Hall of Fame and failures feed EVOLVE;
13. owner idea injection guarantees next-available slot;
14. owner idea is scored identically to others;
15. direct context editing/version restore works;
16. `/status` exposes current execution state;
17. `/ranking`, `/top`, `/history`, `/lineage` expose history;
18. `/report` persists/retrieves generation report;
19. every recoverable failure receives no more than two recovery attempts;
20. successful recovery continues automatically;
21. two failed attempts stop safely and notify owner;
22. restart does not duplicate ideas/evaluations;
23. autopilot remains OFF after bootstrap;
24. no embeddings/vector DB/knowledge graph/operator-evolution subsystem exists.

---

## 24. Definition of self-evolving v1

Self-evolving means:

- successive generations are derived from evaluated prior generations;
- strong directions can reproduce/combine;
- failures influence repair/avoidance;
- historical winners remain visible;
- exploration continuously introduces new roots;
- owner feedback can steer future generations;
- owner ideas can enter the population;
- the loop can run repeatedly without human ideation;
- runtime can recover from ordinary transient failures.

It does **not** mean every piece of architecture evolves.

The hypothesis being tested is:

> **Do successive generations produce materially better candidates for the mission than the initial generation?**

---

## 25. Deferred

Only after v1 evidence justifies complexity:

- embeddings for thousands of ideas;
- automated external research;
- dynamic context creation/removal;
- mutation-operator statistics;
- experiment execution;
- market feedback;
- knowledge graph;
- web dashboard;
- multiple missions.

---

## 26. Final instruction to Codex

Implement the smallest observable reliable system satisfying this document.

Do not preserve old experimental complexity.

Do not silently alter requirements.

If an implementation detail must differ because of the existing VPS/repository, choose the smallest safe equivalent, document the deviation, and continue.

Before declaring success, pass the acceptance criteria and send the Telegram readiness message.

Do not run the first live generation automatically.
