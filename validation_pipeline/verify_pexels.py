"""Non-persisting Pexels search, download, and image-policy canary."""

from __future__ import annotations

import time
from urllib.error import HTTPError

from .config import Settings
from .images import PexelsClient
from .studio import inspect_media


def verify(client, *, pause=time.sleep):
    # These are read-only requests. A transient upstream 5xx must still produce
    # a real validated photo within this bound; authentication/data errors stop.
    for attempt in range(3):
        try:
            photo, source = client.select(
                "calm professional conversation", "people", used_ids=set()
            )
            inspected = inspect_media(source, "image/jpeg")
            if inspected["width"] < 1080 or inspected["height"] < 1080:
                raise ValueError("Pexels canary returned an undersized source")
            return photo, inspected
        except (RuntimeError, HTTPError) as error:
            upstream = error if isinstance(error, HTTPError) else error.__cause__
            if not isinstance(upstream, HTTPError) or not 500 <= upstream.code <= 599 or attempt == 2:
                raise
            pause(2 ** attempt)


def main() -> None:
    client = PexelsClient(Settings.from_environment().pexels_api_key)
    photo, inspected = verify(client)
    print(f"Pexels source canary: OK ({photo.photo_id}, {inspected['width']}x{inspected['height']})")


if __name__ == "__main__":
    main()
