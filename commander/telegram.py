"""Authenticated, side-effect-free Telegram control-plane adapter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .ids import display_ref
from .model import EntityKind
from .service import Commander
from .research import CreativeIdeationResearchService


class TelegramUnauthorized(PermissionError):
    pass


@dataclass(frozen=True, slots=True)
class TelegramReply:
    chat_id: int
    text: str
    callback_query_id: str | None = None


class TelegramControlPlane:
    """Translate Telegram updates into Commander commands.

    Network receipt and delivery belong to a webhook/polling transport. This
    class accepts decoded updates and returns a reply, making authentication and
    command behavior deterministic and independently testable.
    """

    def __init__(
        self,
        commander: Commander,
        *,
        allowed_user_ids: set[int],
        allowed_chat_ids: set[int],
        research_service: CreativeIdeationResearchService | None = None,
    ) -> None:
        if not allowed_user_ids or not allowed_chat_ids:
            raise ValueError("Telegram allowlists must not be empty")
        self.commander = commander
        self.allowed_user_ids = frozenset(allowed_user_ids)
        self.allowed_chat_ids = frozenset(allowed_chat_ids)
        self.research_service = research_service

    def handle_update(self, update: Mapping[str, Any]) -> TelegramReply:
        if "callback_query" in update:
            callback = update["callback_query"]
            message = callback.get("message") or {}
            user_id = int(callback["from"]["id"])
            chat_id = int(message["chat"]["id"])
            self._authorize(user_id, chat_id)
            text = self._handle_command(str(callback.get("data", "")), user_id)
            return TelegramReply(chat_id, text, str(callback["id"]))

        message = update.get("message")
        if not isinstance(message, Mapping):
            raise ValueError("update has no supported message or callback query")
        user_id = int(message["from"]["id"])
        chat_id = int(message["chat"]["id"])
        self._authorize(user_id, chat_id)
        text = self._handle_command(str(message.get("text", "")), user_id)
        return TelegramReply(chat_id, text)

    def authorize(self, user_id: int, chat_id: int) -> None:
        self._authorize(user_id, chat_id)

    def _authorize(self, user_id: int, chat_id: int) -> None:
        if user_id not in self.allowed_user_ids or chat_id not in self.allowed_chat_ids:
            raise TelegramUnauthorized("Telegram user or chat is not authorized")

    def _handle_command(self, raw: str, user_id: int) -> str:
        command, _, argument = raw.strip().partition(" ")
        command = command.split("@", 1)[0].lower()
        actor = f"telegram:{user_id}"
        if command == "/status":
            status = self.commander.status()
            return (
                f"Commander {'STOPPED' if status['emergency_stop'] else 'active'}\n"
                f"Running experiments: {status['running_experiments']}\n"
                f"Pending approvals: {status['pending_approvals']}\n"
                f"Queued tasks: {status['queued_tasks']}\n"
                f"Policy: v{status['policy_version']}"
            )
        if command == "/queue":
            approvals = self.commander.pending_approval_requests()
            if not approvals:
                return "No pending approvals."
            return "Pending approvals:\n" + "\n".join(
                f"{display_ref('approval', item.id)} {item.id} {item.attributes['command']}"
                for item in approvals
            )
        if command == "/policy":
            policy = self.commander.policy
            return (
                f"Policy v{policy.version}\n"
                f"Emergency default: {policy.emergency_stop}\n"
                f"Max running experiments: {policy.max_running_experiments}\n"
                f"Max experiment budget minor: {policy.max_experiment_budget_minor}\n"
                f"Automatic decision confidence: {policy.decision_confidence_threshold:g}\n"
                f"Deployment allowed: {policy.allow_deployment}\n"
                f"Digest: {policy.digest}"
            )
        if command in {"/stop", "stop"}:
            self.commander.set_emergency_stop(True, actor=actor)
            return "Emergency stop enabled. New autonomous writes are blocked."
        if command in {"/resume", "resume"}:
            self.commander.set_emergency_stop(False, actor=actor)
            return "Emergency stop disabled. Policy gates remain active."
        if command in {"/approve", "approve"}:
            request = self.commander.store.get_entity(argument.strip())
            experiment = self.commander.approve_experiment(request, approved_by=actor)
            return f"Approved. Experiment {experiment.id} is running."
        if command in {"/reject", "reject"}:
            request = self.commander.store.get_entity(argument.strip())
            self.commander.reject_approval(request, rejected_by=actor)
            return "Approval request rejected."
        if command == "/reasoning":
            entity = self.commander.store.get_entity(argument.strip())
            if entity.kind not in {EntityKind.DECISION, EntityKind.AUDIT_EVENT}:
                return "Reasoning summaries are available for decisions and audit events."
            return str(entity.attributes.get("reasoning_summary", "No reasoning summary recorded."))
        if command == "/feedback":
            parts = argument.split(maxsplit=2)
            if len(parts) < 2:
                raise ValueError("usage: /feedback <creative-uuid> <1-5> [comment]")
            creative = self.commander.store.get_entity(parts[0])
            feedback, updates = self.commander.record_creative_feedback(
                creative=creative,
                rating=int(parts[1]),
                comment=parts[2] if len(parts) > 2 else "",
                actor=actor,
            )
            return (
                f"Feedback {feedback.id} recorded. "
                f"Updated {len(updates)} component weights with full ID lineage."
            )
        if command == "/graph":
            parts = argument.split(maxsplit=1)
            view = parts[0].lower() if parts else "summary"
            entity_id = parts[1] if len(parts) > 1 else None
            return self._format_graph(self.commander.graph_snapshot(view, entity_id))
        if command == "/research":
            if self.research_service is None:
                return (
                    "Creative research is installed but its provider is not configured. "
                    "Add OPENAI_API_KEY to the VPS runtime environment, then restart Commander."
                )
            sources, hypotheses = self.research_service.run(argument, actor=actor)
            lines = [f"{item.id} {item.attributes['claim'][:110]}" for item in hypotheses]
            return (
                f"Creative research stored: {len(sources)} sources, {len(hypotheses)} proposed hypotheses.\n"
                + "\n".join(lines)
                + "\nGenerate with: /creative from <hypothesis-id>"
            )
        return "Commands: /research <creative topic> /creative from <hypothesis-id> /status /queue /graph [hypotheses|weights|creative <id>] /policy /approve <id> /reject <id> /feedback <creative-id> <1-5> [comment] /reasoning <id> /stop /resume"

    @staticmethod
    def _format_graph(snapshot: Mapping[str, Any]) -> str:
        view = snapshot["view"]
        if view == "summary":
            counts = ", ".join(
                f"{kind}={count}" for kind, count in snapshot["entity_counts"].items()
            ) or "empty"
            recent = "\n".join(f"{kind} {entity_id}" for entity_id, kind in snapshot["recent"])
            return f"Graph: {counts}\nEdges: {snapshot['relationship_count']}\nRecent:\n{recent or 'none'}"
        if view == "hypotheses":
            lines = []
            for item in snapshot["hypotheses"]:
                sources = ",".join(item["source_ids"]) or "none"
                lines.append(f"{item['id']} [{item['status']}] {item['claim'][:100]}\n  sources: {sources}")
            return "Hypotheses:\n" + ("\n".join(lines) or "none")
        if view == "weights":
            lines = [
                f"{item['weight']:.2f} {item['kind']} {item['id']} {item['value']}"
                for item in snapshot["components"]
            ]
            return "Component weights:\n" + ("\n".join(lines) or "none")
        return (
            f"Creative {snapshot['creative_id']}\n"
            f"Components: {', '.join(snapshot['component_ids']) or 'none'}\n"
            f"Feedback: {', '.join(snapshot['feedback_ids']) or 'none'}\n"
            f"Weight updates: {', '.join(snapshot['weight_update_ids']) or 'none'}"
        )
