"""Deterministic texture assets shared by registered Studio templates."""

from __future__ import annotations

from functools import lru_cache
from io import BytesIO
import hashlib
import random
from typing import Any


PHONE_TEXTURE_PRESETS = ("grain", "concrete", "travertine")

# These integer seeds preserve the exact pixels produced by the retired
# renderer's v2 texture generator without retaining a dependency on that
# renderer or its template identity.
_SEEDS = {
    "grain": 564125333442312893440405364265769435827096487257815635134932298495496502355252929153786052319051237119409400407348672988458568822922499390687946349520768406547735384839103555726764399223435958986115692997540,
    "concrete": 9464452570233706952834663923845495166046415421802927364148247568038537823481242356592603596657560242724495343597641067946039753419195370097900750829918993815141675479272846138941900532159285229259486732334691626286,
    "travertine": 620262363642836218860972534913138389272948665784856099822012700486632025390829569440465293162054659172636619952357452454289538868098528243457155931057382929994410881256600541042694497658212741433460737488624443440100324,
}


@lru_cache(maxsize=len(PHONE_TEXTURE_PRESETS))
def texture_asset(preset: str) -> dict[str, Any]:
    """Return the exact deterministic texture used by Phone Metrics."""

    from PIL import Image, ImageDraw

    if preset not in PHONE_TEXTURE_PRESETS:
        raise ValueError("Studio texture preset is invalid")
    rng = random.Random(_SEEDS[preset])
    canvas_size = 192 if preset == "grain" else 540
    image = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    if preset == "grain":
        for _ in range(4100):
            value = rng.choice((0, 255))
            alpha = rng.randint(3, 20)
            draw.point(
                (rng.randrange(192), rng.randrange(192)),
                fill=(value, value, value, alpha),
            )
    elif preset == "concrete":
        for _ in range(3100):
            x, y = rng.randrange(canvas_size), rng.randrange(canvas_size)
            radius = rng.randint(1, 7)
            tone = rng.choice((24, 48, 76, 188, 216, 240))
            draw.ellipse(
                (x - radius, y - radius, x + radius, y + radius),
                fill=(tone, tone, tone, rng.randint(3, 17)),
            )
        for _ in range(520):
            x, y = rng.randrange(canvas_size), rng.randrange(canvas_size)
            draw.ellipse(
                (x, y, x + rng.randint(1, 4), y + rng.randint(1, 3)),
                fill=(12, 12, 12, rng.randint(16, 36)),
            )
    else:
        for y in range(0, canvas_size, 9):
            tone = rng.choice((42, 70, 205, 232))
            draw.line(
                ((0, y + rng.randint(-2, 2)), (canvas_size, y + rng.randint(-2, 2))),
                fill=(tone, tone, tone, rng.randint(4, 15)),
                width=rng.choice((1, 1, 2)),
            )
        for _ in range(760):
            x, y = rng.randrange(canvas_size), rng.randrange(canvas_size)
            radius_x, radius_y = rng.randint(2, 11), rng.randint(1, 3)
            tone = rng.choice((22, 48, 214))
            draw.ellipse(
                (x - radius_x, y - radius_y, x + radius_x, y + radius_y),
                fill=(tone, tone, tone, rng.randint(8, 30)),
            )
    output = BytesIO()
    image.save(output, format="PNG", optimize=False)
    data = output.getvalue()
    return {
        "bytes": data,
        "mime_type": "image/png",
        "sha256": hashlib.sha256(data).hexdigest(),
    }
