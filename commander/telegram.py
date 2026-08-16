"""Authenticated, side-effect-free Telegram control-plane adapter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Mapping

from .ids import display_ref
from .model import EntityKind
from .service import Commander
from .research import CreativeIdeationResearchService
from .research_agents import RESEARCH_AGENTS, research_agent

if TYPE_CHECKING:
    from .ad_generation import AdGenerationEngine


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
        ad_engine: AdGenerationEngine | None = None,
    ) -> None:
        if not allowed_user_ids or not allowed_chat_ids:
            raise ValueError("Telegram allowlists must not be empty")
        self.commander = commander
        self.allowed_user_ids = frozenset(allowed_user_ids)
        self.allowed_chat_ids = frozenset(allowed_chat_ids)
        self.research_service = research_service
        self.ad_engine = ad_engine

    def handle_update(self, update: Mapping[str, Any]) -> TelegramReply:
        if "callback_query" in update:
            callback = update["callback_query"]
            message = callback.get("message") or {}
            user_id = int(callback["from"]["id"])
            chat_id = int(message["chat"]["id"])
            self._authorize(user_id, chat_id)
            text = self._handle_command(str(callback.get("data", "")), user_id, chat_id)
            return TelegramReply(chat_id, text, str(callback["id"]))

        message = update.get("message")
        if not isinstance(message, Mapping):
            raise ValueError("update has no supported message or callback query")
        user_id = int(message["from"]["id"])
        chat_id = int(message["chat"]["id"])
        self._authorize(user_id, chat_id)
        text = self._handle_command(str(message.get("text", "")), user_id, chat_id)
        return TelegramReply(chat_id, text)

    def authorize(self, user_id: int, chat_id: int) -> None:
        self._authorize(user_id, chat_id)

    def _authorize(self, user_id: int, chat_id: int) -> None:
        if user_id not in self.allowed_user_ids or chat_id not in self.allowed_chat_ids:
            raise TelegramUnauthorized("Telegram user or chat is not authorized")

    def _handle_command(self, raw: str, user_id: int, chat_id: int) -> str:
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
        if command == "/estimate":
            if self.ad_engine is None:
                raise ValueError("ad generation is not configured")
            parts = argument.split(maxsplit=3)
            if len(parts) < 3:
                raise ValueError(
                    "usage: reply /estimate <predicted-CTR%> <1-5 rating> [feedback]"
                )
            slot = self.ad_engine.record_estimate(
                creative_id=parts[0],
                predicted_ctr=float(parts[1].removesuffix("%")),
                rating=int(parts[2]),
                comment=parts[3] if len(parts) > 3 else "",
                actor=actor,
            )
            return (
                f"Estimate saved for {slot.context.code} before conclusion generation. "
                "Its producing context is now examining the final image and your feedback."
            )
        if command == "/ads":
            if self.ad_engine is None:
                raise ValueError("ad generation is not configured")
            action, _, value = argument.strip().partition(" ")
            if action == "from":
                raise ValueError(
                    "select the idea through Idea Evolution; use /idea <id> then Generate 10 ads"
                )
            if action == "status":
                batch = (
                    self.ad_engine.repository.batch(value)
                    if value
                    else self.ad_engine.repository.latest_batch(chat_id)
                )
                status = self.ad_engine.status(batch.campaign_id)
                return (
                    f"Ad batch {status['batch_id']} — {status['status']}\n"
                    f"Images: {status['images']}/10; estimates: {status['estimates']}/10; "
                    f"conclusions: {status['conclusions']}/10\n"
                    f"Current image: {status['current_position'] or '-'}\n"
                    f"Last error: {status['last_error'] or 'none'}"
                )
            if action == "continue" and value:
                batch = self.ad_engine.continue_batch(value)
                return f"Ad batch {batch.campaign_id} resumed from preserved work."
            if action == "ranking":
                batch = (
                    self.ad_engine.repository.batch(value)
                    if value
                    else self.ad_engine.repository.latest_batch(chat_id)
                )
                lines = []
                for item in self.ad_engine.ranking(batch.campaign_id):
                    conclusion = item["conclusion"]
                    lines.append(
                        f"{item['rank']}. {item['context_code']} {item['predicted_ctr']:g}% "
                        f"· {item['rating']}/5 · {item['creative_id']}\n"
                        f"   Feedback: {str(conclusion['feedback_interpretation'])[:90]}\n"
                        f"   Effective: {str(conclusion['effective_elements'])[:80]}\n"
                        f"   Improve: {str(conclusion['improvements'])[:80]}\n"
                        f"   Intent fulfilled: {'yes' if conclusion['fulfilled_context_intent'] else 'no'}\n"
                        f"   Next: {str(conclusion['recommended_direction'])[:90]}"
                    )
                return (f"Ad ranking {batch.campaign_id}\n" + "\n".join(lines))[:4096]
            raise ValueError("usage: /ads status [batch-id] | continue <batch-id> | ranking [batch-id]")
        if command == "/ad_contexts":
            self._require_ads()
            return "\n".join(
                f"{item['code']} v{item['version']} {'ON' if item['active'] else 'OFF'} — {item['name']}"
                for item in self.ad_engine.contexts()
            )
        if command.startswith("/ad_context"):
            return self._ad_context_command(command, argument, actor)
        if command == "/graph":
            parts = argument.split(maxsplit=1)
            view = parts[0].lower() if parts else "summary"
            entity_id = parts[1] if len(parts) > 1 else None
            return self._format_graph(self.commander.graph_snapshot(view, entity_id))
        if command == "/research":
            agent_command, _, topic = argument.strip().partition(" ")
            if not topic.strip():
                raise ValueError("usage: /research <creative|product|design|engineering> <topic>")
            agent = research_agent(agent_command)
            if self.research_service is None:
                return (
                    "Creative research is installed but its provider is not configured. "
                    "Add OPENAI_API_KEY to the VPS runtime environment, then restart Commander."
                )
            sources, hypotheses = self.research_service.run(topic, actor=actor, agent=agent)
            lines = [f"{item.id} {item.attributes['claim'][:110]}" for item in hypotheses]
            return (
                f"{agent.owner_agent} research stored: {len(sources)} sources, {len(hypotheses)} proposed hypotheses.\n"
                + "\n".join(lines)
                + f"\nConsume with: {agent.downstream}"
            )
        return "Commands: /research <creative|product|design|engineering> <topic> /creative from <hypothesis-id> /ads status [id] /ads continue <id> /ads ranking [id] /estimate <creative-id> <CTR%> <1-5> [feedback] /ad_contexts /ad_context A01 /status /queue /graph [hypotheses|weights|creative <id>] /policy /approve <id> /reject <id> /feedback <creative-id> <1-5> [comment] /reasoning <id> /stop /resume"

    def _require_ads(self) -> None:
        if self.ad_engine is None:
            raise ValueError("ad generation is not configured")

    def _ad_context_command(self, command: str, argument: str, actor: str) -> str:
        self._require_ads()
        assert self.ad_engine is not None
        code, _, value = argument.strip().partition(" ")
        code = code.upper()
        current = self.ad_engine.context(code)
        if command == "/ad_context":
            return f"{code} v{current['version']} {current['name']}\n\n{current['prompt']}"
        if command == "/ad_context_history":
            return "\n".join(
                f"v{item['version']} {item['name']} — {item.get('changed_by', '')} {item.get('change_note') or ''}"
                for item in self.ad_engine.context_history(code)
            )
        if command in {"/ad_context_enable", "/ad_context_disable"}:
            self.ad_engine.set_context_active(code, command.endswith("enable"))
            return f"{code} updated. A new ad batch still requires active A01-A10."
        if command == "/ad_context_restore":
            version = self.ad_engine.restore_context(code, int(value), actor=actor)
            return f"{code} restored as v{version}; existing batch snapshots are unchanged."
        if command == "/ad_context_set" and value:
            version = self.ad_engine.revise_context(
                code,
                name=str(current["name"]),
                prompt=value,
                actor=actor,
                note="prompt edited",
            )
            return f"{code} saved as v{version}; future batches only."
        if command == "/ad_context_name" and value:
            version = self.ad_engine.revise_context(
                code,
                name=value,
                prompt=str(current["prompt"]),
                actor=actor,
                note="name edited",
            )
            return f"{code} saved as v{version}; future batches only."
        raise ValueError("invalid ad-context command")

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
                lines.append(f"{item['id']} [{item['status']}] {item['owner_agent']}\n  {item['claim'][:100]}\n  sources: {sources}")
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
