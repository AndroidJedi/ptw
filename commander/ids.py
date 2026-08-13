"""Permanent identifier generation without third-party dependencies."""

from __future__ import annotations

import secrets
import time
import uuid


def new_uuid7(*, timestamp_ms: int | None = None) -> str:
    """Return an RFC 9562 UUIDv7 string.

    UUIDv7 carries a Unix-millisecond prefix for useful database locality while
    retaining 74 random bits. Display references must never replace this value.
    """

    milliseconds = int(time.time() * 1000) if timestamp_ms is None else timestamp_ms
    if not 0 <= milliseconds < 1 << 48:
        raise ValueError("timestamp_ms must fit in 48 bits")

    random_bits = secrets.randbits(74)
    value = milliseconds << 80
    value |= 0x7 << 76
    value |= ((random_bits >> 62) & 0xFFF) << 64
    value |= 0b10 << 62
    value |= random_bits & ((1 << 62) - 1)
    return str(uuid.UUID(int=value))


def display_ref(kind: str, entity_id: str) -> str:
    """Return a non-authoritative, human-friendly reference."""

    return f"{kind[:3].upper()}-{entity_id.replace('-', '')[:8].upper()}"
