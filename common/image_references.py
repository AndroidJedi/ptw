"""Bounded single-use reference inputs. No bytes are written to the job database."""
from __future__ import annotations

import threading
import uuid
from typing import Any


class EphemeralImageReferences:
    def __init__(self, *, ttl_seconds: float = 600, capacity: int = 2) -> None:
        self.ttl_seconds = ttl_seconds
        self.capacity = capacity
        self._lock = threading.Lock()
        self._items: dict[str, tuple[dict[str, Any], threading.Timer]] = {}

    def put(self, image: dict[str, Any]) -> str:
        with self._lock:
            if len(self._items) >= self.capacity:
                raise RuntimeError("Temporary image input capacity is full; retry after current generation")
            key = uuid.uuid4().hex
            timer = threading.Timer(self.ttl_seconds, self.discard, args=(key,))
            timer.daemon = True
            self._items[key] = (dict(image), timer)
            timer.start()
            return key

    def consume(self, key: str) -> dict[str, Any]:
        with self._lock:
            item = self._items.pop(key, None)
        if item is None:
            raise KeyError("Reference expired or was consumed; upload it again")
        image, timer = item
        timer.cancel()
        return image

    def discard(self, key: str) -> None:
        try:
            self.consume(key)
        except KeyError:
            pass


def persistable_image_request(request: dict, references: EphemeralImageReferences) -> tuple[dict, str | None]:
    """Replace the validated upload with metadata before Jsonb serialization."""
    result = dict(request)
    images = result.pop("input_images", None)
    artifacts = result.pop("input_artifacts", None)
    if images is not None and artifacts is not None:
        raise ValueError("only one structured image input family is allowed")
    inputs = images if images is not None else artifacts
    if inputs is None:
        return result, None
    image = inputs[0]
    key = references.put(image)
    result["input_reference"] = {"id": key, **{k: v for k, v in image.items() if k != "bytes_base64"}}
    return result, key
