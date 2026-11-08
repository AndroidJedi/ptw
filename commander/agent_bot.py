"""Durable Commander-mediated Business Researcher MVP.

The first agent implementation is intentionally bounded and provider-free. It
still exercises the architecture that matters here: every agent invocation is
persisted as a run, the researcher can address only Commander, and Commander
decides whether a request is allowed, needs owner approval, or is denied.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import re
import threading
from typing import Any, Callable, Mapping
from uuid import UUID, uuid4


AGENT_DEFINITIONS = (
    {
        "id": "commander",
        "name": "Commander",
        "role": "Coordinator",
        "description": "Decides how to satisfy requests and supervises all agent communication.",
    },
    {
        "id": "business_researcher",
        "name": "Business Researcher",
        "role": "Specialist",
        "description": "Tests business ideas, surfaces unknowns and proposes the next research action.",
    },
)

PERMISSIONS = (
    {"agent_id": "commander", "capability": "read", "mode": "allowed", "reason": "Can inspect the current task context."},
    {"agent_id": "commander", "capability": "research", "mode": "allowed", "reason": "Can run bounded research actions."},
    {"agent_id": "commander", "capability": "create_task", "mode": "allowed", "reason": "Can delegate work to registered agents."},
    {"agent_id": "commander", "capability": "ask_user", "mode": "allowed", "reason": "Can ask for missing decision-critical context."},
    {"agent_id": "commander", "capability": "system_expansion", "mode": "approval_required", "reason": "Changing the available system needs owner approval."},
    {"agent_id": "commander", "capability": "external_actions", "mode": "approval_required", "reason": "External side effects need owner approval."},
    {"agent_id": "business_researcher", "capability": "read", "mode": "allowed", "reason": "Can read its assigned task context."},
    {"agent_id": "business_researcher", "capability": "research", "mode": "allowed", "reason": "Can analyze the idea and supplied research results."},
    {"agent_id": "business_researcher", "capability": "create_task", "mode": "approval_required", "reason": "Only Commander can create delegated tasks."},
    {"agent_id": "business_researcher", "capability": "ask_user", "mode": "allowed", "reason": "May surface a missing input through Commander."},
    {"agent_id": "business_researcher", "capability": "system_expansion", "mode": "denied", "reason": "A specialist cannot expand system permissions."},
    {"agent_id": "business_researcher", "capability": "external_actions", "mode": "denied", "reason": "A specialist cannot perform external side effects."},
)

PERMISSION_MAP = {(item["agent_id"], item["capability"]): item["mode"] for item in PERMISSIONS}
CONVERSATION_KEYS = ("id", "title", "status", "created_at", "updated_at")
TASK_KEYS = ("id", "conversation_id", "task_type", "status", "assigned_agent", "context", "result", "error", "started_at", "finished_at", "created_at", "updated_at")
RUN_KEYS = ("id", "conversation_id", "task_id", "agent_id", "status", "input", "output", "created_at", "finished_at")
MESSAGE_KEYS = ("id", "conversation_id", "task_id", "sender", "recipient", "kind", "body", "request_id", "sequence", "created_at")
ACTION_KEYS = ("id", "conversation_id", "task_id", "requested_by", "action_type", "mode", "status", "reason", "payload", "created_at", "decided_at")


def _json(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if value is None:
        return {}
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return {}
    return value


def _jsonb(value: Any) -> Any:
    """Use psycopg's JSON adapter while keeping unit-test doubles simple."""
    try:
        from psycopg.types.json import Jsonb
        return Jsonb(value)
    except ModuleNotFoundError:
        return json.dumps(value, ensure_ascii=False)


def _iso(value: Any) -> Any:
    return value.isoformat() if hasattr(value, "isoformat") else value


def _text(value: Any, limit: int = 4000) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _idea_digest(idea: str) -> str:
    return hashlib.sha256(idea.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class AgentRequest:
    request_type: str
    question: str
    reason: str
    capability: str


class BusinessResearcherAgent:
    """A small real agent boundary with a deterministic MVP reasoning core."""

    agent_id = "business_researcher"

    def run(self, idea: str, context: Mapping[str, Any]) -> dict[str, Any]:
        market = _text(context.get("target_market"), 180)
        if not market:
            return {
                "kind": "request",
                "request": AgentRequest(
                    "ask_user",
                    "Какой рынок исследовать первым: страна, регион или язык аудитории?",
                    "Без целевого рынка оценка спроса и конкуренции будет недостоверной.",
                    "ask_user",
                ),
            }
        if not context.get("market_research"):
            return {
                "kind": "request",
                "request": AgentRequest(
                    "research_market",
                    f"Нужно проверить спрос и альтернативы для рынка «{market}».",
                    "Промежуточная гипотеза требует отдельного исследовательского шага до финальной оценки.",
                    "research",
                ),
            }

        research = context["market_research"]
        return {
            "kind": "final",
            "report": {
                "summary": f"Идея имеет проверяемый потенциал на рынке «{market}», но пока остаётся гипотезой.",
                "audience": f"Первые пользователи: люди и команды на рынке «{market}», у которых регулярно возникает описанная проблема.",
                "problem": "Ценность выглядит правдоподобной, если продукт сокращает заметное повторяющееся усилие или риск.",
                "demand": "Спрос не подтверждён живыми интервью или продажами; следующий шаг — 5–10 разговоров с целевыми пользователями.",
                "competition": research["competitors"],
                "monetization": "Проверить подписку или оплату за использование после подтверждения частоты проблемы.",
                "risks": [
                    "описание идеи может быть слишком широким",
                    "конкуренты и заменители не проверены по текущим данным",
                    "нет количественного сигнала готовности платить",
                ],
                "next_steps": [
                    "сформулировать один узкий сегмент и обещание результата",
                    "провести 5–10 интервью на выбранном рынке",
                    "сравнить результаты с двумя ближайшими альтернативами",
                ],
                "research_note": "Это bounded MVP-анализ, а не подтверждение фактов из внешнего веб-поиска.",
                "market_signal": research["signals"],
            },
        }


class CommanderDecisionEngine:
    """Policy gate and bounded tools used by Commander, never by the specialist."""

    def decide(self, request: AgentRequest) -> tuple[str, str]:
        mode = PERMISSION_MAP.get(("commander", request.capability), "denied")
        if mode == "denied":
            return mode, "Commander policy denies this capability."
        return mode, "Commander accepted the request within its current permission set."

    def research_market(self, idea: str, market: str) -> dict[str, Any]:
        terms = [part for part in re.findall(r"[\wА-Яа-яІіЇїЄє-]{4,}", idea.lower()) if part not in {"это", "для", "идея", "продукт"}]
        focus = ", ".join(terms[:3]) or "описанную проблему"
        return {
            "market": market,
            "signals": [
                f"Проверить повторяемость проблемы «{focus}» у выбранного сегмента.",
                "Сравнить частоту задачи и готовность платить, а не только интерес к концепции.",
            ],
            "competitors": [
                "Прямые продукты с тем же обещанием результата — проверить вручную.",
                "Текущие рабочие процессы, таблицы и услуги — считать заменителями.",
                "Результат пока является списком гипотез, не каталогом проверенных компаний.",
            ],
        }


class AgentBotService:
    """PostgreSQL-backed hub with one serialized worker per research task."""

    def __init__(self, database_url: str, *, connection_factory: Callable[[], Any] | None = None):
        self.database_url = database_url
        self._connection_factory = connection_factory
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="commander-bot")
        self._lock = threading.RLock()
        self._closed = False
        self.researcher = BusinessResearcherAgent()
        self.decisions = CommanderDecisionEngine()
        self._recover()

    @contextmanager
    def connection(self):
        if self._connection_factory:
            with self._connection_factory() as database:
                yield database
            return
        import psycopg
        with psycopg.connect(self.database_url, connect_timeout=5) as database:
            yield database

    def _recover(self) -> None:
        """A restart does not replay a completed mutation, but resumes queued work."""
        with self.connection() as database:
            database.execute("UPDATE commander_bot_runs SET status='interrupted', finished_at=clock_timestamp() WHERE status='running'")
            database.execute("UPDATE commander_bot_tasks SET status='queued', updated_at=clock_timestamp() WHERE status='running'")
            rows = database.execute("SELECT id FROM commander_bot_tasks WHERE status='queued'").fetchall()
        for row in rows:
            self._submit(str(row[0]))

    def _submit(self, task_id: str) -> None:
        with self._lock:
            if not self._closed:
                self._executor.submit(self._run_task, task_id)

    def capabilities(self) -> dict[str, Any]:
        return {"schema": "ptw.commander-bot.v1", "agents": list(AGENT_DEFINITIONS), "permissions": list(PERMISSIONS)}

    def create_conversation(self, title: str = "") -> dict[str, Any]:
        identifier = uuid4()
        with self.connection() as database:
            database.execute(
                "INSERT INTO commander_bot_conversations(id,title,status) VALUES(%s,%s,'idle')",
                (identifier, _text(title, 120) or "Новая оценка бизнес-идеи"),
            )
        return self.conversation(str(identifier))

    def status(self) -> dict[str, Any]:
        with self.connection() as database:
            rows = database.execute(
                "SELECT id,title,status,created_at,updated_at FROM commander_bot_conversations ORDER BY created_at DESC LIMIT 30"
            ).fetchall()
        return {"available": True, "agents": self._agent_status(), "permissions": list(PERMISSIONS), "conversations": [self._row(row, CONVERSATION_KEYS) for row in rows]}

    def _agent_status(self) -> list[dict[str, Any]]:
        with self.connection() as database:
            rows = database.execute(
                "SELECT agent_id,count(*) FROM commander_bot_runs WHERE status='running' GROUP BY agent_id"
            ).fetchall()
        active = {str(row[0]): int(row[1]) for row in rows}
        return [{**item, "status": "working" if active.get(item["id"]) else "idle", "active_runs": active.get(item["id"], 0)} for item in AGENT_DEFINITIONS]

    @staticmethod
    def _row(row: Any, keys: tuple[str, ...] | None = None) -> dict[str, Any]:
        if hasattr(row, "keys"):
            value = dict(row)
        else:
            value = dict(zip(keys or tuple(str(index) for index in range(len(row))), row))
        return {key: _iso(item) for key, item in value.items()}

    def conversation(self, conversation_id: str) -> dict[str, Any]:
        identifier = UUID(conversation_id)
        with self.connection() as database:
            conversation = database.execute("SELECT * FROM commander_bot_conversations WHERE id=%s", (identifier,)).fetchone()
            if not conversation:
                raise KeyError(conversation_id)
            messages = database.execute("SELECT * FROM commander_bot_messages WHERE conversation_id=%s ORDER BY sequence", (identifier,)).fetchall()
            tasks = database.execute("SELECT * FROM commander_bot_tasks WHERE conversation_id=%s ORDER BY created_at", (identifier,)).fetchall()
            runs = database.execute("SELECT * FROM commander_bot_runs WHERE conversation_id=%s ORDER BY created_at", (identifier,)).fetchall()
            actions = database.execute("SELECT * FROM commander_bot_actions WHERE conversation_id=%s ORDER BY created_at", (identifier,)).fetchall()
        return {
            "conversation": self._row(conversation, CONVERSATION_KEYS),
            "messages": [self._public_message(item) for item in messages],
            "tasks": [self._public_record(item, TASK_KEYS) for item in tasks],
            "runs": [self._public_record(item, RUN_KEYS) for item in runs],
            "actions": [self._public_record(item, ACTION_KEYS) for item in actions],
            "agents": list(AGENT_DEFINITIONS),
            "permissions": list(PERMISSIONS),
        }

    def _public_record(self, row: Any, keys: tuple[str, ...] | None = None) -> dict[str, Any]:
        result = self._row(row, keys)
        for key in ("context", "input", "output", "payload", "details"):
            if key in result:
                result[key] = _json(result[key])
        return result

    def _public_message(self, row: Any) -> dict[str, Any]:
        result = self._public_record(row, MESSAGE_KEYS)
        body = result.pop("body", {})
        result["text"] = _text(body.get("text", ""), 8000) if isinstance(body, dict) else ""
        result["data"] = body if isinstance(body, dict) else {}
        return result

    def send_message(self, conversation_id: str, request_id: str, message: str) -> dict[str, Any]:
        identifier = UUID(conversation_id)
        request = UUID(request_id)
        message = _text(message, 8000)
        if not message:
            raise ValueError("Message is required")
        task_id: str | None = None
        with self.connection() as database:
            exists = database.execute("SELECT conversation_id FROM commander_bot_messages WHERE request_id=%s", (request,)).fetchone()
            if exists:
                if exists[0] != identifier:
                    raise ValueError("Request ID already belongs to another conversation")
                return self.conversation(conversation_id)
            conversation = database.execute("SELECT status FROM commander_bot_conversations WHERE id=%s FOR UPDATE", (identifier,)).fetchone()
            if not conversation:
                raise KeyError(conversation_id)
            task = database.execute(
                "SELECT id,status,context FROM commander_bot_tasks WHERE conversation_id=%s ORDER BY created_at DESC LIMIT 1 FOR UPDATE",
                (identifier,),
            ).fetchone()
            database.execute(
                "INSERT INTO commander_bot_messages(id,conversation_id,sender,recipient,kind,body,request_id) VALUES(%s,%s,'user','commander','user_input',%s,%s)",
                (uuid4(), identifier, _jsonb({"text": message}), request),
            )
            if task and task[1] == "waiting_user":
                task_id = str(task[0])
                context = _json(task[2])
                context["target_market"] = message
                database.execute(
                    "UPDATE commander_bot_tasks SET context=%s,status='queued',updated_at=clock_timestamp() WHERE id=%s",
                    (_jsonb(context), task[0]),
                )
            elif task and task[1] == "waiting_approval":
                raise ValueError("Commander Bot is waiting for approval of the pending action")
            elif not task or task[1] in {"completed", "failed", "cancelled"}:
                task_id = str(uuid4())
                database.execute(
                    "INSERT INTO commander_bot_tasks(id,conversation_id,task_type,status,assigned_agent,context) VALUES(%s,%s,'business_research','queued','business_researcher',%s)",
                    (task_id, identifier, _jsonb({"idea": message, "idea_sha256": _idea_digest(message)})),
                )
            else:
                raise ValueError("Commander Bot is already processing this conversation")
            database.execute("UPDATE commander_bot_conversations SET status='working',updated_at=clock_timestamp() WHERE id=%s", (identifier,))
        if task_id:
            self._submit(task_id)
        return self.conversation(conversation_id)

    def decide_action(self, conversation_id: str, action_id: str, decision: str) -> dict[str, Any]:
        if decision not in {"approved", "rejected"}:
            raise ValueError("Decision must be approved or rejected")
        identifier = UUID(conversation_id)
        action = UUID(action_id)
        task_id: str | None = None
        with self.connection() as database:
            row = database.execute("SELECT id,task_id,status,mode,action_type FROM commander_bot_actions WHERE id=%s AND conversation_id=%s FOR UPDATE", (action, identifier)).fetchone()
            if not row:
                raise KeyError(action_id)
            if row[2] != "pending" or row[3] != "approval_required":
                raise ValueError("Action is no longer awaiting approval")
            task_id = str(row[1])
            database.execute("UPDATE commander_bot_actions SET status=%s,decided_at=clock_timestamp() WHERE id=%s", (decision, action))
            database.execute(
                "INSERT INTO commander_bot_messages(id,conversation_id,task_id,sender,recipient,kind,body) VALUES(%s,%s,%s,'commander','user',%s,%s)",
                (uuid4(), identifier, row[1], "action_decision", _jsonb({"text": f"Action {decision}: {row[4]}"})),
            )
            if decision == "approved":
                database.execute("UPDATE commander_bot_tasks SET status='queued',updated_at=clock_timestamp() WHERE id=%s", (row[1],))
            else:
                database.execute("UPDATE commander_bot_tasks SET status='failed',updated_at=clock_timestamp() WHERE id=%s", (row[1],))
        if decision == "approved" and task_id:
            self._submit(task_id)
        return self.conversation(conversation_id)

    def stop_task(self, conversation_id: str, task_id: str) -> dict[str, Any]:
        with self.connection() as database:
            database.execute("UPDATE commander_bot_tasks SET status='cancelled',updated_at=clock_timestamp() WHERE id=%s AND conversation_id=%s AND status IN ('queued','running','waiting_user','waiting_approval')", (UUID(task_id), UUID(conversation_id)))
            database.execute("UPDATE commander_bot_conversations SET status='cancelled',updated_at=clock_timestamp() WHERE id=%s", (UUID(conversation_id),))
        return self.conversation(conversation_id)

    def _run_task(self, task_id: str) -> None:
        task_uuid = UUID(task_id)
        try:
            with self.connection() as database:
                task = database.execute("SELECT * FROM commander_bot_tasks WHERE id=%s FOR UPDATE", (task_uuid,)).fetchone()
                if not task or task[3] != "queued":
                    return
                database.execute("UPDATE commander_bot_tasks SET status='running',started_at=coalesce(started_at,clock_timestamp()),updated_at=clock_timestamp() WHERE id=%s", (task_uuid,))
                task = database.execute("SELECT * FROM commander_bot_tasks WHERE id=%s", (task_uuid,)).fetchone()
            task_record = self._public_record(task, TASK_KEYS)
            context = task_record.get("context", {})
            idea = _text(context.get("idea"), 8000)
            run_id = uuid4()
            with self.connection() as database:
                database.execute("INSERT INTO commander_bot_runs(id,conversation_id,task_id,agent_id,status,input) VALUES(%s,%s,%s,'business_researcher','running',%s)", (run_id, task[1], task_uuid, _jsonb({"idea": idea, "context": context})))
            result = self.researcher.run(idea, context)
            with self.connection() as database:
                persisted_result = json.loads(json.dumps(result, default=lambda item: item.__dict__, ensure_ascii=False))
                database.execute("UPDATE commander_bot_runs SET status='completed',output=%s,finished_at=clock_timestamp() WHERE id=%s", (_jsonb(persisted_result), run_id))
            if result["kind"] == "final":
                self._finish_task(task, result["report"])
                return
            request: AgentRequest = result["request"]
            self._handle_request(task, request)
        except Exception:
            with self.connection() as database:
                database.execute("UPDATE commander_bot_tasks SET status='failed',error='agent_execution_failed',updated_at=clock_timestamp() WHERE id=%s", (task_uuid,))
                database.execute("UPDATE commander_bot_conversations SET status='failed',updated_at=clock_timestamp() WHERE id=(SELECT conversation_id FROM commander_bot_tasks WHERE id=%s)", (task_uuid,))

    def _handle_request(self, task: Any, request: AgentRequest) -> None:
        conversation_id = task[1]
        action_id = uuid4()
        mode, decision_note = self.decisions.decide(request)
        with self.connection() as database:
            database.execute("INSERT INTO commander_bot_messages(id,conversation_id,task_id,sender,recipient,kind,body) VALUES(%s,%s,%s,'business_researcher','commander','agent_request',%s)", (uuid4(), conversation_id, task[0], _jsonb({"text": request.question, "request_type": request.request_type, "reason": request.reason})))
            database.execute("INSERT INTO commander_bot_runs(id,conversation_id,task_id,agent_id,status,input,output,finished_at) VALUES(%s,%s,%s,'commander','completed','{}',%s,clock_timestamp())", (uuid4(), conversation_id, task[0], _jsonb({"decision": mode, "note": decision_note})))
            database.execute("INSERT INTO commander_bot_actions(id,conversation_id,task_id,requested_by,action_type,mode,status,reason,payload) VALUES(%s,%s,%s,'business_researcher',%s,%s,%s,%s,%s)", (action_id, conversation_id, task[0], request.request_type, mode, "pending" if mode == "approval_required" else "executed" if mode == "allowed" else "denied", request.reason, _jsonb({"question": request.question})))
            if mode == "allowed" and request.request_type == "ask_user":
                database.execute("INSERT INTO commander_bot_messages(id,conversation_id,task_id,sender,recipient,kind,body) VALUES(%s,%s,%s,'commander','user','commander_question',%s)", (uuid4(), conversation_id, task[0], _jsonb({"text": request.question, "reason": request.reason})))
                database.execute("UPDATE commander_bot_tasks SET status='waiting_user',updated_at=clock_timestamp() WHERE id=%s", (task[0],))
                database.execute("UPDATE commander_bot_conversations SET status='waiting_user',updated_at=clock_timestamp() WHERE id=%s", (conversation_id,))
                return
            if mode == "allowed" and request.request_type == "research_market":
                context = _json(task[5])
                research = self.decisions.research_market(context.get("idea", ""), context.get("target_market", ""))
                context["market_research"] = research
                database.execute("UPDATE commander_bot_tasks SET context=%s,status='queued',updated_at=clock_timestamp() WHERE id=%s", (_jsonb(context), task[0]))
                database.execute("UPDATE commander_bot_actions SET payload=%s WHERE id=%s", (_jsonb({"research": research}), action_id))
                database.execute("INSERT INTO commander_bot_messages(id,conversation_id,task_id,sender,recipient,kind,body) VALUES(%s,%s,%s,'commander','business_researcher','action_result',%s)", (uuid4(), conversation_id, task[0], _jsonb({"text": "Исследование выполнено. Продолжай оценку.", "research": research})))
                database.execute("UPDATE commander_bot_conversations SET status='working',updated_at=clock_timestamp() WHERE id=%s", (conversation_id,))
            elif mode == "approval_required":
                database.execute("INSERT INTO commander_bot_messages(id,conversation_id,task_id,sender,recipient,kind,body) VALUES(%s,%s,%s,'commander','user','approval_required',%s)", (uuid4(), conversation_id, task[0], _jsonb({"text": "Нужно разрешение владельца на действие системы.", "reason": request.reason})))
                database.execute("UPDATE commander_bot_tasks SET status='waiting_approval',updated_at=clock_timestamp() WHERE id=%s", (task[0],))
                database.execute("UPDATE commander_bot_conversations SET status='waiting_approval',updated_at=clock_timestamp() WHERE id=%s", (conversation_id,))
            else:
                database.execute("UPDATE commander_bot_tasks SET status='failed',error='permission_denied',updated_at=clock_timestamp() WHERE id=%s", (task[0],))
        if mode == "allowed" and request.request_type == "research_market":
            self._submit(str(task[0]))

    def _finish_task(self, task: Any, report: Mapping[str, Any]) -> None:
        conversation_id = task[1]
        text = report["summary"]
        with self.connection() as database:
            database.execute("INSERT INTO commander_bot_runs(id,conversation_id,task_id,agent_id,status,input,output,finished_at) VALUES(%s,%s,%s,'commander','completed','{}',%s,clock_timestamp())", (uuid4(), conversation_id, task[0], _jsonb({"decision": "deliver_result"})))
            database.execute("INSERT INTO commander_bot_messages(id,conversation_id,task_id,sender,recipient,kind,body) VALUES(%s,%s,%s,'commander','user','final_result',%s)", (uuid4(), conversation_id, task[0], _jsonb({"text": text, "report": report})))
            database.execute("UPDATE commander_bot_tasks SET status='completed',result=%s,finished_at=clock_timestamp(),updated_at=clock_timestamp() WHERE id=%s", (_jsonb(report), task[0]))
            database.execute("UPDATE commander_bot_conversations SET status='completed',updated_at=clock_timestamp() WHERE id=%s", (conversation_id,))

    def close(self) -> None:
        with self._lock:
            self._closed = True
        self._executor.shutdown(wait=False, cancel_futures=True)
