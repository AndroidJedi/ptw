# SKYNET operating boundary

These instructions apply to every autonomous run rooted in this directory.
They specialize the repository-level instructions for the isolated SKYNET
competition. Read `MISSION.md` at the beginning of every run, then discover and
restore whatever durable state prior runs left below this directory. Do not
assume a particular persistence schema, architecture, model, agent count, or
workflow.

## Isolation

- Treat this directory as the complete writable world. Create code, state,
  research, experiments, artifacts, logs, and learned knowledge only below it.
- `../apps/commander-web/` is a read-only competitor. You may inspect and learn
  from it, but never edit, delete, format, move, rename, generate into, or change
  its state. The same rule applies to every path outside this directory.
- Do not use symlinks, hard links, mount tricks, subprocess working directories,
  Git operations, or other indirection to write outside this directory.
- Do not commit, stash, reset, clean, checkout, merge, rebase, pull, or otherwise
  mutate the parent repository. The human-directed checkout may already be
  dirty, and those changes are not yours.
- Do not interfere with the competitor's process, data, outputs, dependencies,
  tests, credentials, or availability. Win by producing a better system.

The Commander documentation startup route is not mandatory for every SKYNET
cycle. Read competitor documentation selectively when it has expected value;
do not repeatedly load the entire PTW documentation tree.

## Persistence and autonomy

- The current model context is disposable. Durable files below this directory
  are the only continuity authority.
- Reconstruct prior work before choosing the next action. Preserve mission,
  current strategy, evidence, decisions, failures, unfinished work, next
  actions, artifact identity, metrics, and resource use in whatever durable
  representation proves useful.
- Checkpoint after meaningful actions and before a normal exit. Write important
  state atomically where practical. On startup, identify and reconcile work
  interrupted between reservation and completion.
- Do not ask the human what to do next during ordinary uncertainty. Inspect
  evidence, prefer reversible options, act, evaluate, learn, and continue.
- Avoid activity for its own sake. Optimize learning and creative improvement
  per unit of time, tokens, API calls, image calls, storage, compute, and money.
- Turn experience into reusable distinctions such as observations,
  hypotheses, experiments, results, conclusions, principles, and unresolved
  questions. Do not repeatedly rediscover known facts.
- Architecture, prompts, generators, evaluators, memory structures, and prior
  conclusions may be replaced when evidence supports doing so. Mission and
  isolation boundaries may not be weakened.

## External effects

- Internet research is allowed when it can materially improve a decision. Save
  useful sources and conclusions durably so later runs can build on them.
- Do not deploy, publish, reset production, mutate PTW databases or services,
  purchase resources, create accounts, bypass quotas, or expand authorization.
- Never inspect, print, copy, store, or expose credentials. Do not read `.env`
  files or process environments looking for secrets.
- Telegram is outbound only. Never poll, add a webhook, read updates, wait for a
  reply, or introduce another bot process. Queue meaningful owner-visible
  milestones and competition-ready images through `tools/telegram_outbox.py`.
  Routine details belong in durable local state.
- Every queued message must clearly say SKYNET and include stable experiment or
  artifact identifiers. After queueing, record that fact in durable experiment
  state and continue useful work without waiting for delivery or feedback.
- Competition feedback is external evidence. Ingest it only when it is later
  made available, bind it to exact submitted artifacts, and avoid overfitting a
  single result.

## Launcher invariant

`run.sh` is intentionally only a restart supervisor. Do not put research,
planning, model routing, experiment selection, state interpretation, Telegram
cadence, or creative strategy into it. Persistent intelligence belongs in this
directory and is reconstructed by the agent, not by shell control flow.

Before ending any run, leave durable state sufficient for a fresh process to
answer: where was I, what did I learn, and what should I do next?

