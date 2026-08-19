"""Durable, bounded Telegram projections of authoritative Laval run state."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from commander.ids import new_uuid7

from .laval_repository import LavalRepository


STAGE_MARKERS = {
    "completed": "✅",
    "partial": "⚠️",
    "failed": "❌",
    "running": "▶️",
    "paused": "⏸",
    "pending": "▫️",
    "stale": "◽️",
}


def format_laval_status_message(status: Mapping[str, Any], event: str) -> str:
    run = status["run"]
    stages = list(status.get("stages") or [])
    cost = status.get("cost") or {}
    completed = sum(1 for stage in stages if stage.get("status") in {"completed", "partial"})
    current = str(run.get("current_stage") or "CREATED")
    lines = [
        f"Idea Laval · {str(run.get('status') or event).upper()}",
        f"Run {run['id']}",
        f"Current: {current} · {completed}/{len(stages)} stages",
        f"Evidence: {run.get('evidence_mode', 'unknown')}",
        (
            f"Cost: ${float(cost.get('provider_actual_usd') or cost.get('total_usd') or 0):.4f} actual · "
            f"${float(cost.get('provider_reserved_usd') or 0):.4f} reserved · "
            f"${float(cost.get('max_spend_usd') or .05):.2f} max"
        ),
    ]
    if run.get("error_text"):
        lines.append(f"Error: {str(run['error_text'])[:700]}")
    recovery = status.get("recovery") or {}
    tasks = recovery.get("provider_tasks") or {}
    if run.get("status") == "failed" and tasks.get("total"):
        lines.append(
            "Recovery: "
            f"{tasks.get('completed', 0)}/{tasks.get('total', 0)} completed · "
            f"{tasks.get('submitted', 0)} still submitted · "
            f"{tasks.get('persisted_remote_ids', 0)} remote IDs saved."
        )
        lines.append("Resume in the app reuses saved task IDs; it does not repost or rebill them.")
    if run.get("awaiting_reason") == "awaiting_trends_provider":
        if status.get("resume_with_market_signals_available"):
            lines.append("Action: use Resume with Market Signals in the web app; Google Trends is optional.")
        else:
            lines.append("Blocked legacy run: provider action is required in the web app.")
    elif run.get("status") == "paused" and current in (run.get("approval_gates") or []):
        lines.append(f"Action: review and approve {current} in the app.")
    lines.append("Stages:")
    for stage in stages:
        stage_status = str(stage.get("status") or "unknown")
        marker = STAGE_MARKERS.get(stage_status, "·")
        lines.append(
            f"{marker} S{int(stage.get('ordinal') or 0):02d} {stage.get('stage')} — "
            f"{stage_status} #{int(stage.get('attempt') or 0)}"
        )
    lines.append("Web: https://provethemwrong-86123.firebaseapp.com")
    return "\n".join(lines)[:4096]


class LavalTelegramNotifier:
    def __init__(self, repository: LavalRepository, chat_ids: Sequence[int]) -> None:
        self.repository = repository
        self.store = repository.store
        self.chat_ids = tuple(sorted({int(value) for value in chat_ids}))

    def enqueue(self, run_id: str, event: str, *, force: bool = False, actor: str = "system") -> int:
        status = self.repository.status(run_id)
        run = status["run"]
        current = next(
            (stage for stage in status["stages"] if stage["stage"] == run.get("current_stage")),
            {},
        )
        text = format_laval_status_message(status, event)
        queued = 0
        with self.store.transaction() as connection:
            if connection.execute("SELECT to_regclass('public.commander_outbox')").fetchone()[0] is None:
                return 0
            for chat_id in self.chat_ids:
                dedupe = None if force else (
                    f"telegram:{run_id}:{event}:{run.get('status')}:{run.get('current_stage')}:"
                    f"{current.get('attempt', 0)}:{chat_id}"
                )
                action_id = new_uuid7()
                inserted = connection.execute(
                    """INSERT INTO laval_run_actions(
                           id,run_id,action,stage,actor,previous_status,outcome,details,dedupe_key
                       ) VALUES(%s,%s,'telegram_status_enqueued',%s,%s,%s,'queued',%s::jsonb,%s)
                       ON CONFLICT(dedupe_key) DO NOTHING RETURNING id""",
                    (
                        action_id,
                        run_id,
                        run.get("current_stage"),
                        actor,
                        run.get("status"),
                        self.store.json({"event": event, "chat_id": chat_id}),
                        dedupe,
                    ),
                ).fetchone()
                if not inserted:
                    continue
                connection.execute(
                    """INSERT INTO commander_outbox(id,topic,aggregate_id,payload)
                       VALUES(%s,'telegram.send_message',NULL,%s::jsonb)""",
                    (new_uuid7(), self.store.json({"chat_id": chat_id, "text": text, "source": "idea-laval"})),
                )
                queued += 1
        return queued
