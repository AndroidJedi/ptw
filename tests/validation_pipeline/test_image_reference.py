from io import BytesIO
import base64
import json
import unittest
from unittest.mock import Mock

from validation_pipeline.image_reference import decode_reference, generation_request, generate_image, MAX_REFERENCE_BASE64_CHARS


def upload(format='PNG', size=(320, 640)):
    from PIL import Image, PngImagePlugin
    output = BytesIO()
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text('private-comment', 'DO-NOT-STORE-THIS')
    Image.new('RGB', size, '#e03675').save(output, format=format, **({'pnginfo': metadata} if format == 'PNG' else {}))
    return {'mime_type': {'PNG': 'image/png', 'JPEG': 'image/jpeg', 'WEBP': 'image/webp'}[format], 'bytes_base64': base64.b64encode(output.getvalue()).decode()}


class ImageReferenceTests(unittest.TestCase):
    def test_normalizes_formats_without_metadata_or_composition_crop(self):
        from PIL import Image
        for format in ('PNG', 'JPEG', 'WEBP'):
            with self.subTest(format=format):
                data = decode_reference(upload(format, (1024, 3072)))
                image = Image.open(BytesIO(data))
                self.assertEqual('PNG', image.format)
                self.assertEqual((683, 2048), image.size)
                self.assertEqual({}, image.info)
                self.assertNotIn(b'DO-NOT-STORE-THIS', data)

    def test_exif_orientation_is_applied_before_metadata_is_removed(self):
        from PIL import Image
        source = Image.new('RGB', (128, 256), '#f02564')
        exif = source.getexif()
        exif[274] = 6
        output = BytesIO()
        source.save(output, 'JPEG', exif=exif)
        normalized = decode_reference({'mime_type': 'image/jpeg', 'bytes_base64': base64.b64encode(output.getvalue()).decode()})
        result = Image.open(BytesIO(normalized))
        self.assertEqual((256, 128), result.size)
        self.assertEqual({}, result.info)

    def test_rejects_bad_inputs_before_provider(self):
        valid = upload()
        for value in ({}, [], {**valid, 'path': '/tmp/file'}, {**valid, 'mime_type': 'image/svg+xml'},
                      {**valid, 'mime_type': 'image/jpeg'}, {**valid, 'bytes_base64': '!!!!'},
                      {**valid, 'bytes_base64': 'a' * (MAX_REFERENCE_BASE64_CHARS + 1)}, upload(size=(32, 64)),
                      upload(size=(5000, 5000)), upload(size=(64, 8192))):
            with self.subTest(type=type(value)):
                with self.assertRaises(ValueError):
                    decode_reference(value)

    def test_request_is_shared_optional_and_rejects_ambiguous_sources(self):
        request = {'base_sha256': 'a'*64, 'visual_direction': 'Keep the shape, change the background'}
        self.assertNotIn('reference_image', generation_request(request))
        options = generation_request({**request, 'reference_image': upload()})
        self.assertIsInstance(options['reference_image'], bytes)
        for extra in ({'enhance_current': 'yes'}, {'reference_image': upload(), 'enhance_current': True}, {'saved_reference_id': 'x'}):
            with self.assertRaises(ValueError):
                generation_request({**request, **extra})

    def test_shared_pipeline_passes_text_and_image_and_only_returns_result(self):
        provider = Mock()
        provider.generate.return_value = {'bytes': b'result', 'source': {}}
        reference = decode_reference(upload())
        result = generate_image(provider, 'Keep the shape, change the background', reference_image=reference, uploaded_reference=True)
        self.assertEqual(reference, provider.generate.call_args.kwargs['reference_image'])
        self.assertIn('Keep the shape, change the background', provider.generate.call_args.args[0])
        self.assertIn('Infer what to preserve', provider.generate.call_args.args[0])
        self.assertEqual('uploaded_reference', result['source']['generation_mode'])
        self.assertNotIn('bytes_base64', json.dumps(result['source']))

    def test_both_http_routes_decode_the_same_operation_input_and_reject_invalid_upload(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from validation_pipeline.studio_routes import studio_creative_router
        from validation_pipeline.landing_routes import landing_page_router
        service = Mock()
        service.mutate.return_value = {'state_sha256': 'b' * 64}
        app = FastAPI()
        app.include_router(studio_creative_router(service, prefix='/studio'))
        app.include_router(landing_page_router(service, prefix='/landing'))
        request = {'base_sha256': 'a'*64, 'visual_direction': 'Keep the object, change the background', 'reference_image': upload()}
        for path in ('/studio/projects/project/creatives/creative/phone-screen/generate',
                     '/landing/projects/project/pages/page/visuals/hero_visual/generate',
                     '/landing/projects/project/pages/page/visuals/visual_break_visual/generate'):
            service.reset_mock()
            with TestClient(app) as client:
                response = client.post(path, json=request)
                self.assertEqual(200, response.status_code, response.text)
                self.assertEqual(decode_reference(request['reference_image']), service.mutate.call_args.kwargs['reference_image'])
                self.assertNotIn('reference_image', response.json())
                service.reset_mock()
                invalid = client.post(path, json={**request, 'reference_image': {'mime_type': 'image/png', 'bytes_base64': 'invalid'}})
                self.assertEqual(400, invalid.status_code)
                service.mutate.assert_not_called()
