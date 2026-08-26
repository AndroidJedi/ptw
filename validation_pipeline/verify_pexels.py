"""Non-persisting Pexels search, download, and image-policy canary."""

from __future__ import annotations

from .config import Settings
from .images import PexelsClient
from .studio import inspect_media


def main() -> None:
    client = PexelsClient(Settings.from_environment().pexels_api_key)
    photo, source = client.select(
        "calm professional conversation", "people", used_ids=set()
    )
    inspected = inspect_media(source, "image/jpeg")
    if inspected["width"] < 1080 or inspected["height"] < 1080:
        raise SystemExit("Pexels canary returned an undersized source")
    print(f"Pexels source canary: OK ({photo.photo_id}, {inspected['width']}x{inspected['height']})")


if __name__ == "__main__":
    main()
