"""Authenticated Telegram notification and emergency-control adapter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .service import Commander


class TelegramUnauthorized(PermissionError):
    pass


@dataclass(frozen=True, slots=True)
class TelegramReply:
    chat_id: int
    text: str
    callback_query_id: str | None = None


class TelegramControlPlane:
    """Expose only help, bounded status, and emergency stop in Telegram."""

    def __init__(
        self,
        commander: Commander,
        *,
        allowed_user_ids: set[int],
        allowed_chat_ids: set[int],
        web_url: str = "https://provethemwrong-86123.web.app",
        **_removed_command_services: object,
    ) -> None:
        if not allowed_user_ids or not allowed_chat_ids:
            raise ValueError("Telegram allowlists must not be empty")
        self.commander = commander
        self.allowed_user_ids = frozenset(allowed_user_ids)
        self.allowed_chat_ids = frozenset(allowed_chat_ids)
        self.web_url = web_url.rstrip("/")

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
        text = self._handle_command(str(message.get("text") or message.get("caption") or ""), user_id)
        return TelegramReply(chat_id, text)

    def authorize(self, user_id: int, chat_id: int) -> None:
        self._authorize(user_id, chat_id)

    def _authorize(self, user_id: int, chat_id: int) -> None:
        if user_id not in self.allowed_user_ids or chat_id not in self.allowed_chat_ids:
            raise TelegramUnauthorized("Telegram user or chat is not authorized")

    def _handle_command(self, raw: str, user_id: int) -> str:
        command = raw.strip().partition(" ")[0].split("@", 1)[0].lower()
        if command in {"/help", "help"}:
            return (
                "PTW Telegram: /help, /status, /stop.\n"
                f"Усе керування, review і генерація: {self.web_url}"
            )
        if command in {"/status", "status"}:
            status = self.commander.status()
            return (
                f"Commander {'STOPPED' if status['emergency_stop'] else 'active'}\n"
                f"Active jobs: {status['queued_tasks']}\n"
                f"Pending reviews: {status['pending_approvals']}\n"
                f"Web: {self.web_url}"
            )
        if command in {"/stop", "stop"}:
            self.commander.set_emergency_stop(True, actor=f"telegram:{user_id}")
            return (
                "Emergency stop enabled. New autonomous writes are blocked.\n"
                f"Recovery and all other controls: {self.web_url}"
            )
        return f"Ця команда доступна лише у web Commander: {self.web_url}"
