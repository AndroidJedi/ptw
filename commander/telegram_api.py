"""Small Telegram Bot API client with no credential logging."""

from __future__ import annotations

import json
import mimetypes
import secrets
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Mapping


class TelegramApiError(RuntimeError):
    pass


class TelegramBotClient:
    def __init__(self, token: str, *, timeout_seconds: int = 30) -> None:
        if not token:
            raise ValueError("Telegram bot token is required")
        self._base_url = f"https://api.telegram.org/bot{token}"
        self._file_url = f"https://api.telegram.org/file/bot{token}"
        self.timeout_seconds = timeout_seconds

    def send_message(self, chat_id: int, text: str) -> Mapping[str, Any]:
        return self._form("sendMessage", {"chat_id": str(chat_id), "text": text})

    def send_photo(self, chat_id: int, path: Path, caption: str = "") -> Mapping[str, Any]:
        boundary = f"ptw-{secrets.token_hex(16)}"
        fields = {"chat_id": str(chat_id), "caption": caption}
        body = bytearray()
        for name, value in fields.items():
            body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode())
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        body.extend(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"photo\"; filename=\"{path.name}\"\r\nContent-Type: {mime}\r\n\r\n".encode()
        )
        body.extend(path.read_bytes())
        body.extend(f"\r\n--{boundary}--\r\n".encode())
        request = urllib.request.Request(
            f"{self._base_url}/sendPhoto",
            data=bytes(body),
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        return self._open(request)

    def download_photo(self, file_id: str, destination: Path) -> Path:
        result = self._form("getFile", {"file_id": file_id})
        file_path = str(result["file_path"])
        destination.parent.mkdir(parents=True, exist_ok=True)
        request = urllib.request.Request(f"{self._file_url}/{urllib.parse.quote(file_path)}")
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            content_length = int(response.headers.get("Content-Length", "0"))
            if content_length > 20 * 1024 * 1024:
                raise TelegramApiError("Telegram photo exceeds 20 MB limit")
            data = response.read(20 * 1024 * 1024 + 1)
        if len(data) > 20 * 1024 * 1024:
            raise TelegramApiError("Telegram photo exceeds 20 MB limit")
        destination.write_bytes(data)
        return destination

    def set_webhook(self, url: str, secret_token: str) -> Mapping[str, Any]:
        return self._form(
            "setWebhook",
            {"url": url, "secret_token": secret_token, "drop_pending_updates": "false"},
        )

    def answer_callback_query(self, callback_query_id: str) -> Mapping[str, Any]:
        return self._form("answerCallbackQuery", {"callback_query_id": callback_query_id})

    def get_updates(self) -> list[Mapping[str, Any]]:
        request = urllib.request.Request(f"{self._base_url}/getUpdates")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read())
        except Exception as error:
            raise TelegramApiError(f"Telegram API request failed: {type(error).__name__}") from error
        if not payload.get("ok") or not isinstance(payload.get("result"), list):
            raise TelegramApiError(str(payload.get("description", "Unable to read updates")))
        return [item for item in payload["result"] if isinstance(item, Mapping)]

    def _form(self, method: str, values: Mapping[str, str]) -> Mapping[str, Any]:
        request = urllib.request.Request(
            f"{self._base_url}/{method}",
            data=urllib.parse.urlencode(values).encode(),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        return self._open(request)

    def _open(self, request: urllib.request.Request) -> Mapping[str, Any]:
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read())
        except Exception as error:
            raise TelegramApiError(f"Telegram API request failed: {type(error).__name__}") from error
        if not payload.get("ok"):
            raise TelegramApiError(str(payload.get("description", "Telegram API rejected request")))
        result = payload.get("result")
        return result if isinstance(result, Mapping) else {"result": result}
