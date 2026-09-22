"""Offline, digest-pinned background removal for authored cutout image slots."""
from __future__ import annotations

from functools import lru_cache
from io import BytesIO
from pathlib import Path
import hashlib

from PIL import Image, ImageFilter


MODEL_PATH = Path(__file__).with_name("studio_assets") / "cutout-model" / "u2netp.onnx"
MODEL_SHA256 = "309c8469258dda742793dce0ebea8e6dd393174f89934733ecc8b14c76f4ddd8"


@lru_cache(maxsize=1)
def _session():
    import onnxruntime as ort

    if hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest() != MODEL_SHA256:
        raise RuntimeError("Template cutout model digest mismatch")
    options = ort.SessionOptions()
    options.intra_op_num_threads = 2
    return ort.InferenceSession(str(MODEL_PATH), sess_options=options, providers=["CPUExecutionProvider"])


@lru_cache(maxsize=8)
def cutout_png(data: bytes) -> bytes:
    """Keep genuine alpha; otherwise extract a foreground without altering raw art."""
    with Image.open(BytesIO(data)) as original:
        if original.width * original.height > 16_000_000:
            raise ValueError("Cutout image exceeds the pixel limit")
        original.load()
        image = original.convert("RGBA")
    alpha = image.getchannel("A")
    if alpha.getextrema()[0] < 250:
        return data

    import numpy as np

    sample = image.convert("RGB").resize((320, 320), Image.Resampling.LANCZOS)
    pixels = np.asarray(sample, dtype=np.float32)
    pixels /= max(float(pixels.max()), 1.0)
    pixels = (pixels - np.array([.485, .456, .406], dtype=np.float32)) / np.array([.229, .224, .225], dtype=np.float32)
    tensor = np.transpose(pixels, (2, 0, 1))[None, ...].astype(np.float32)
    session = _session()
    prediction = session.run(None, {session.get_inputs()[0].name: tensor})[0][0, 0]
    low, high = float(prediction.min()), float(prediction.max())
    if high - low < 1e-6:
        raise ValueError("Foreground could not be separated from the background")
    mask = Image.fromarray(np.uint8((prediction - low) * (255.0 / (high - low))))
    mask = mask.resize(image.size, Image.Resampling.LANCZOS)
    mask = mask.point(lambda value: 255 if value >= 127 else 0).filter(ImageFilter.MedianFilter(3))
    extent = mask.getbbox()
    if extent is None or extent == (0, 0, image.width, image.height):
        raise ValueError("Foreground could not be separated from the background")
    image.putalpha(mask)
    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()
