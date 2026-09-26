"""Owner-requested offline source art must survive reusable-template application."""
from copy import deepcopy
import hashlib
from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from PIL import Image

from validation_pipeline import template_assets
from validation_pipeline.template_assets import ASSET_ROOT, asset_bytes, asset_metadata
from validation_pipeline.template_components import definition, new_component, normalize_document, render, seed, sha
from validation_pipeline.template_previews import geometry


def document():
    doc = seed('post')
    doc['canvas'] = {'width': 1080, 'height': 1080, 'mobile_height': 1080}
    doc['components'] = [
        {**new_component('identity', 'image', 'brand', [50, 30, 300, 85], 'Image'),
         'asset_id': 'sanlarix_logo_v1', 'fit': 'contain'},
        {**new_component('visual', 'image', 'hero', [50, 150, 900, 700], 'Image'),
         'asset_id': 'sanlarix_business_v1', 'fit': 'cover'},
    ]
    return normalize_document(doc)


class TemplateImageAssetTests(unittest.TestCase):
    def test_source_and_raster_integrity_offline_render_and_fixed_identity(self):
        doc = document()
        registered = definition({'surface': 'landing', 'template_id': 'source_art',
            'template_version': 1, 'template_sha256': sha(doc), 'document': doc})
        self.assertEqual(('visual',), registered.capabilities.image_slots)
        for asset in template_assets.IMAGE_ASSET_IDS:
            with self.subTest(asset=asset):
                metadata = asset_metadata(asset)
                self.assertEqual(metadata['source_sha256'], hashlib.sha256((ASSET_ROOT / metadata['source_file']).read_bytes()).hexdigest())
                data, mime = asset_bytes(asset)
                self.assertEqual(metadata['sha256'], hashlib.sha256(data).hexdigest())
                self.assertEqual('image/png', mime)
                with Image.open(BytesIO(data)) as im:
                    im.verify()
        result = render(doc, surface='post')
        self.assertFalse(geometry(result)[1])
        with self.assertRaisesRegex(ValueError, 'cannot be replaced'):
            render(doc, surface='post', assets={'identity': {'bytes': result['bytes'], 'mime_type': 'image/png'}})
        altered = {**template_assets._ASSETS['sanlarix_business_v1'], 'sha256': '0' * 64}
        with patch.dict(template_assets._ASSETS, {'sanlarix_business_v1': altered}):
            with self.assertRaisesRegex(RuntimeError, 'digest mismatch'):
                render(doc, surface='post')
        for kind in ['brand', 'store_badge', 'cutout_image']:
            invalid = deepcopy(doc)
            invalid['components'][0]['type'] = kind
            with self.assertRaises(ValueError):
                normalize_document(invalid)

    def test_project_hero_replaces_photo_and_retains_logo_across_save_and_reopen(self):
        from validation_pipeline.post_template_runtime import post_definition
        from validation_pipeline.post_templates import POST_TEMPLATE_REGISTRY
        from validation_pipeline.studio_workspace import PostStudioWorkspace
        from validation_pipeline.template_registry import TemplateRegistry
        doc = document()
        definition = post_definition({'surface': 'post', 'template_id': 'asset_preservation',
            'template_version': 1, 'template_sha256': sha(doc), 'document': doc})
        registry = TemplateRegistry('post', (*POST_TEMPLATE_REGISTRY.all(), definition))
        replacement = BytesIO()
        Image.new('RGB', (600, 500), '#B34965').save(replacement, format='PNG')
        with tempfile.TemporaryDirectory() as directory:
            workspace = PostStudioWorkspace(Path(directory), template_registry=lambda: registry)
            detail = workspace.detail()
            detail = workspace.switch_template(base_sha256=detail['state_sha256'], template_reference=definition.identity.to_reference(),
                request_id=str(uuid4()), configuration=detail['configuration'], content=detail['content'])
            # A disposable test fixture, never an owner generation/provenance record.
            workspace._store_asset('phone_screen', mime_type='image/png', data=replacement.getvalue(), source={'origin': 'test_fixture'})
            detail = workspace.detail()
            records = workspace._asset_records(detail['configuration'], detail['content'])
            self.assertEqual(asset_bytes('sanlarix_logo_v1')[0], records['identity']['bytes'])
            self.assertEqual(replacement.getvalue(), records['visual']['bytes'])
            result = workspace.render_preview(state_sha256=detail['state_sha256'])
            with Image.open(BytesIO(result['bytes'])) as im:
                self.assertEqual((179, 73, 101), im.convert('RGB').getpixel((540, 540)))
            workspace.save_configuration(base_sha256=detail['state_sha256'], configuration=detail['configuration'], content=detail['content'])
            reopened = PostStudioWorkspace(Path(directory), template_registry=lambda: registry)
            again = reopened.detail()
            self.assertEqual(definition.identity.to_reference(), again['template_reference'])
            self.assertEqual(result['bytes'], reopened.render_preview(state_sha256=again['state_sha256'])['bytes'])
            self.assertEqual(doc, definition.document)
