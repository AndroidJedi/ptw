"""Code-owned lead-form catalog for published Natal landings."""

from __future__ import annotations

from typing import Any


FORM_IDS = ("waitlist", "contact_request", "community_interest")


def form_definition(form_id: str, language: str) -> dict[str, Any]:
    if form_id not in FORM_IDS or language not in {"uk", "en"}:
        raise ValueError("unknown Natal lead form")
    uk = language == "uk"
    common = {
        "email": {"type": "email", "required": True, "label": "Email"},
        "name": {"type": "text", "required": True, "label": "Ім’я" if uk else "Name"},
        "note": {"type": "textarea", "required": False, "label": "Нотатка" if uk else "Note"},
        "telegram_handle": {"type": "text", "required": False, "label": "Telegram"},
    }
    definitions = {
        "waitlist": {
            "fields": [common["email"] | {"name": "email"}],
            "submit_label": "Приєднатися до списку" if uk else "Join waitlist",
        },
        "contact_request": {
            "fields": [common["name"] | {"name": "name"}, common["email"] | {"name": "email"}, common["note"] | {"name": "note"}],
            "submit_label": "Надіслати запит" if uk else "Send request",
        },
        "community_interest": {
            "fields": [common["name"] | {"name": "name"}, common["email"] | {"name": "email"}, common["telegram_handle"] | {"name": "telegram_handle"}],
            "submit_label": "Хочу приєднатися" if uk else "I’m interested",
        },
    }
    return {
        "id": form_id,
        **definitions[form_id],
        "success_copy": (
            "Дякуємо. Ми отримали ваші дані та зв’яжемося з вами."
            if uk else
            "Thanks. We received your details and will contact you."
        ),
    }


def allowed_field_names(form_id: str) -> set[str]:
    return {item["name"] for item in form_definition(form_id, "en")["fields"]}
