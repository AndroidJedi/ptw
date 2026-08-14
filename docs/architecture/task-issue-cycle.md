# Autonomous task and issue cycle

Status: canonical architecture contract
Updated: 2026-08-14

## Decision

Engineering tasks and operational issues are separate durable records. A task
represents owner intent and its outcome. An issue represents a specific failure
encountered while executing a task, including its diagnostic log and resolution
history. Treating failure as only a task status would lose remediation lineage
and make repeated failures indistinguishable.

The operational engineering runner remains in the unrelated-history
`/opt/ptw/platform` deployment. PostgreSQL is its state authority; the GitHub
repository records this architecture and the versioned autonomy policy. The two
repositories must not be merged to achieve integration.

## Lifecycle

```text
TASK queued -> running -> completed
                  |
                  v
                blocked --------------------+
                  |                         |
                  v                         |
ISSUE open -> resolving -> resolved --------+-> TASK running
                    |
                    v
                unresolved -> TASK failed
```

Cancellation may interrupt queued, running, or blocked tasks. Cancelling during
resolution terminates the child executor, marks the issue cancelled, and then
marks the parent task cancelled.

Every transition appends an event. Issue diagnostics are also appended to a
dedicated issue log. Existing rows are never cleared to make a retry look clean.
Payloads are bounded and scrubbed before persistence; credentials, private
chain-of-thought, and raw secret-bearing environment state are excluded.

## Recovery contract

When a resumable stage fails, Commander:

1. Creates `ISSUE-<id>`, links it to `TASK-<id>`, stores the sanitized failure,
   marks the task blocked, and reports both IDs to Telegram.
2. Switches execution to bounded issue resolution. Code or validation failures
   use the isolated Codex resolver; external idempotent operations use bounded
   retry without permitting repository edits.
3. Appends each resolution attempt to the issue log.
4. On resolution, reports it, resumes the parent at its failed stage, and keeps
   all history. A later verification failure becomes another issue rather than
   rewriting the prior one.
5. On exhaustion or a non-resumable failure, marks the issue unresolved and the
   task failed, then reports the inspect command. It does not loop forever.

## Inspection and state transfer

Telegram `/inspect TASK-<id>` returns task state, linked issues, and recent
events. `/inspect ISSUE-<id>` returns failure, resolution, and recent issue-log
entries. Numeric input is accepted as a task ID for compatibility.

For another agent or offline review, the deployment provides:

```sh
python -m engineering.state_export [TASK-<id>|ISSUE-<id>] --output state.json
```

The JSON export is versioned, deterministic, permission-restricted when written
to disk, and secret-scrubbed. With no reference it exports the full Commander
control state. Large binary attachments and credentials are deliberately not
embedded; artifact paths and metadata retain their lineage.

## Production authority

Policy version 2 grants standing authority to merge a validated task pull
request into `main`. Direct main pushes remain forbidden. Commander records the
pre-merge main SHA as the rollback revision and the resulting SHA as the release
revision, reports both, and lets the established main pipeline perform the
production deployment. Merge or release-trigger failures enter the same issue
cycle.

Owner control remains continuous: Telegram acknowledgement includes the task
ID, `/inspect` exposes current state, and `/cancel` interrupts queued, running,
or blocked work. `/stop` remains the wider Commander emergency stop.
