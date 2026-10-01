"""Safe provider failures which may authorize a fresh image attempt."""


class InvalidGeneratedImage(RuntimeError):
    def __init__(self, provider_request_id=None):
        self.provider_request_id = provider_request_id
        super().__init__("The image service returned an incomplete or invalid image.")
