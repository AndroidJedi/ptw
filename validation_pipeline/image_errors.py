"""Safe, bounded provider failures which may authorize a fresh image attempt."""


CONFIRMED_IMAGE_FAILURES = frozenset({
    "invalid_image",  # Legacy receipts and bridge jobs.
    "invalid_png_structure", "invalid_png_checksum", "pixel_decode_failed",
    "dimension_mismatch", "missing_image_result", "save_failed",
})


def classify_image_validation_error(error: Exception) -> str:
    message = str(error)
    if "checksum" in message:
        return "invalid_png_checksum"
    if "aspect ratio" in message or "dimension bounds" in message or "bounded square" in message:
        return "dimension_mismatch"
    if isinstance(error, OSError) or "pixels" in message:
        return "pixel_decode_failed"
    return "invalid_png_structure"


class InvalidGeneratedImage(RuntimeError):
    def __init__(self, provider_request_id=None, failure_code="invalid_image"):
        if failure_code not in CONFIRMED_IMAGE_FAILURES:
            raise ValueError("Unknown image failure code")
        self.provider_request_id = provider_request_id
        self.failure_code = failure_code
        super().__init__("The image service returned an incomplete or invalid image.")
