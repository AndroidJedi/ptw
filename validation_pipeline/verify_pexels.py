"""Non-persisting Pexels download and deterministic render canary."""

from __future__ import annotations

from io import BytesIO

from .config import Settings
from .images import PexelsClient, SquareCreativeRenderer


def main() -> None:
    from PIL import Image

    client = PexelsClient(Settings.from_environment().pexels_api_key)
    photo, source = client.select(
        "calm professional conversation", "people", used_ids=set()
    )
    rendered, digest = SquareCreativeRenderer().render(
        source,
        hook="A clearer next step",
        offer="First assessment free",
        cta="Request access",
        crop_focus="center",
    )
    image = Image.open(BytesIO(rendered))
    if image.format != "JPEG" or image.size != (1080, 1080) or len(digest) != 64:
        raise SystemExit("Pexels render canary produced an invalid artifact")
    print(f"Pexels render canary: OK ({photo.photo_id}, {digest})")


if __name__ == "__main__":
    main()
