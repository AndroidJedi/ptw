import httpx

from common.secrets import EnvironmentSecretStore


def send_telegram(chat_id: int, text: str, *, reply_to_message_id: int | None = None) -> None:
    token = EnvironmentSecretStore().get("TELEGRAM_BOT_TOKEN")
    payload: dict = {"chat_id": chat_id, "text": text}
    if reply_to_message_id:
        payload["reply_parameters"] = {"message_id": reply_to_message_id}
    response = httpx.post(
        f"https://api.telegram.org/bot{token}/sendMessage", json=payload, timeout=10
    )
    response.raise_for_status()

