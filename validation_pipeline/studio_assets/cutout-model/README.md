# Authored Post cutout model

`u2netp.onnx` is the lightweight U²-Net salient-object model published by the
rembg project at
<https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2netp.onnx>.
Its SHA-256 is
`309c8469258dda742793dce0ebea8e6dd393174f89934733ecc8b14c76f4ddd8`.
U²-Net source and weights are attributed to Xuebin Qin and collaborators under
Apache-2.0; the accompanying `LICENSE` is from the upstream repository.

The model runs locally in Validation with no image upload or runtime download.
Only `cutout_image` slots use it, and already-transparent images are preserved.
