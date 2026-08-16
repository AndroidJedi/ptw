# Telegram Control Reference — Idea Evolution v1

Telegram is the primary owner console. Routine control should require no SSH.

## Execution

- `/status` — live mission, generation, phase, progress, leaders, queue, errors, remaining run-series count.
- `/run` — exactly one full generation, report, then stop.
- `/run N` — N generations sequentially; report after each.
- `/run [N]` during an active series — queue N additional generations and
  report the new persisted remaining count.
- `/stop` — gracefully finish current generation and stop before next; preserve remaining count.
- `/continue` — resume a stopped/interrupted run series.
- `/pause` — pause mission and automatic progression.
- `/resume` — resume mission.
- `/autopilot on|off|24h` — scheduled execution.

## Rankings and history

- `/ranking` — all 10 ideas of latest completed generation ranked.
- `/generation N` — ranking for a specific generation.
- `/idea ID` — full idea, score range, critiques, details, parents, guidance.
- `/top [N]` — historical top ideas across every completed generation.
- `/history [N]` — generation-by-generation best/average/worst trend.
- `/lineage ID` — ancestry from parent IDs.

## Reports

- `/report` — latest generation report.
- `/report G7` — report for G7.
- `/reports [N]` — recent report index.

Generation report includes ranking, best/average/worst, delta vs previous generation, historical best, owner ideas, failures, evaluator disagreement, top lineage, guidance, recoveries, calls/tokens.

## Owner ideas

- `/idea_add TEXT` — queue your own candidate.
- `/idea_done` — finish and queue a multi-message idea draft.
- `/idea_abort` — discard the active multi-message idea draft.
- `/idea_queue` — pending submissions.
- `/idea_cancel SUBMISSION_ID` — cancel before insertion.

A pending owner idea is guaranteed a slot in the next generation with capacity.
When a completed batch exists, the new generation retains its highest-rated
candidates and replaces one lowest-rated candidate per owner idea. The prior
generation remains immutable history, and every retained candidate keeps its
parent lineage.

If `/idea_add` reaches Telegram's practical single-message limit, it starts a
durable draft. Send the remaining parts as ordinary messages, then `/idea_done`.

Example:

```text
2 owner ideas
+ latest batch's 8 highest-rated retained ideas
= 10 candidates
```

The omitted lowest-rated candidates remain immutable in their completed source
generation. Owner ideas receive no scoring advantage.

## Feedback

- `/guidance TEXT`
- `/guidance_list`
- `/guidance_clear ID`
- `/feedback IDEA_ID TEXT`
- `/keep IDEA_ID [TEXT]`
- `/reject IDEA_ID [REASON]`

Historical scores are never rewritten.

## Contexts

Stable owner IDs: `C01...C10`.

- `/contexts`
- `/context C03`
- `/context_set C03 TEXT`
- `/context_name C03 NAME`
- `/context_history C03`
- `/context_restore C03 VERSION`
- `/context_enable C03`
- `/context_disable C03`

Owner edits are versioned and affect future calls only.

V1 requires exactly 10 active contexts to run.

## Audit/debug

- `/executions [N]`
- `/errors [N]`
- `/cost`
- `/task`
- `/help`

## Recovery

For each recoverable failing step:

```text
attempt 1
attempt 2 if needed
continue automatically if fixed
stop safely if both fail
```

Telegram receives diagnosis, attempted repair, result, and whether execution continues.

After two failed attempts, completed data and run-series remaining count are preserved. `/continue` may be used after state is healthy.

Production runtime does not rewrite its own source code.

## Free-form examples

The bot should also understand equivalent owner intents:

```text
"покажи текущий рейтинг"
"что сейчас выполняется?"
"добавь мою идею: ..."
"покажи всю историю"
"измени контекст C04: ..."
"остановись после текущего поколения"
```

State-changing actions must still be translated into validated supported commands/actions.
