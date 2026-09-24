"""Deterministic transparent mockup preparation; raw provider bytes remain private."""
from io import BytesIO
import hashlib

from PIL import Image, ImageChops, ImageDraw, ImageOps

from .template_cutout import MODEL_SHA256, cutout_png

PREPARATION_VERSION = "ptw.landing-cutout.v1"


def prepare_mockup(data: bytes) -> tuple[bytes, dict]:
    with Image.open(BytesIO(data)) as original:
        original.load()
        image = original.convert("RGBA")
    raw_size = list(image.size)
    # One transparent pixel is not proof of a transparent surrounding canvas.
    alpha = image.getchannel("A")
    transparent = alpha.histogram()[0]
    native_alpha = transparent >= image.width * image.height * .01
    if not native_alpha:
        # Strip incidental alpha before the existing extractor's native-alpha
        # shortcut; a stray transparent pixel must not leave an opaque rectangle.
        opaque = BytesIO()
        image.convert("RGB").save(opaque, format="PNG")
        image = Image.open(BytesIO(cutout_png(opaque.getvalue()))).convert("RGBA")
        alpha = image.getchannel("A")
        # The saliency model may classify a white screen as a hole. Fill enclosed
        # interiors, retaining all foreground components rather than only the largest.
        silhouette = alpha.point(lambda n: 255 if n >= 127 else 0)
        outside = ImageOps.expand(silhouette, border=1, fill=0)
        ImageDraw.floodfill(outside, (0, 0), 255)
        holes = ImageOps.invert(outside.crop((1, 1, image.width + 1, image.height + 1)))
        alpha = ImageChops.lighter(alpha, holes)
        image.putalpha(alpha)
    extent = alpha.point(lambda n: 255 if n > 8 else 0).getbbox()
    if extent is None or alpha.getextrema()[0] >= 250:
        raise ValueError("Mockup background could not be separated; previous image preserved")
    # Crop transparent canvas only; retain a predictable safety margin and shadows.
    padding = max(2, round(max(extent[2] - extent[0], extent[3] - extent[1]) * .03))
    box = (max(0, extent[0] - padding), max(0, extent[1] - padding),
           min(image.width, extent[2] + padding), min(image.height, extent[3] + padding))
    image = image.crop(box)
    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    prepared = output.getvalue()
    return prepared, {
        "schema": PREPARATION_VERSION,
        "method": "native_alpha" if native_alpha else "pinned_cutout",
        **({"model_sha256": MODEL_SHA256} if not native_alpha else {}),
        "raw_sha256": hashlib.sha256(data).hexdigest(),
        "prepared_sha256": hashlib.sha256(prepared).hexdigest(),
        "raw_size": raw_size, "crop_box": list(box), "padding": padding,
    }
