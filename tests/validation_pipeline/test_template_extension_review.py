"""Exercise reviewed source application without touching the actual checkout."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import review_template_extension as review
from validation_pipeline.template_components import sha


class TemplateExtensionReviewTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name) / 'checkout'
        self.snapshot = Path(directory.name) / 'review/workspace'
        self.name = 'validation_pipeline/template_components.py'
        for base, data in ((self.root, b'original'), (self.snapshot, b'reviewed')):
            path = base / self.name
            path.parent.mkdir(parents=True)
            path.write_bytes(data)
        self.preview = self.snapshot / '.local/template-capability-preview.png'
        self.preview.parent.mkdir()
        self.preview.write_bytes(b'verified-preview')
        self.state = {'capability':'curved_image_mask', 'baseline':{self.name:review.digest(self.root/self.name)}}
        self.state['verified'] = {'capability':'curved_image_mask', 'verification':'passed',
            'sources':{self.name:review.digest(self.snapshot/self.name)},
            'visual_review_sha256':review.digest(self.preview)}
        self.state['review_sha256'] = sha(self.state['verified'])
        self.receipt = self.root/'validation_pipeline/studio_components/capability_reviews/curved_image_mask.json'

    def apply(self):
        review.apply_review(self.snapshot, self.root, self.state, self.state['review_sha256'])

    def test_exact_review_applies_source_and_binds_receipt_without_unrelated_writes(self):
        unrelated = self.root/'owner.txt'
        unrelated.write_bytes(b'preserve me')
        self.apply()
        self.assertEqual(b'reviewed', (self.root/self.name).read_bytes())
        self.assertTrue(self.receipt.is_file())
        self.assertEqual(b'preserve me', unrelated.read_bytes())

    def test_stale_visual_source_and_review_digest_each_fail_before_writing(self):
        self.preview.write_bytes(b'changed visual')
        with self.assertRaisesRegex(ValueError, 'visual preview changed'): self.apply()
        self.preview.write_bytes(b'verified-preview')
        (self.root/self.name).write_bytes(b'owner concurrent work')
        with self.assertRaisesRegex(ValueError, 'Concurrent'): self.apply()
        self.assertEqual(b'owner concurrent work', (self.root/self.name).read_bytes())
        (self.root/self.name).write_bytes(b'original')
        self.state['review_sha256'] = 'a'*64
        with self.assertRaisesRegex(ValueError, 'exact verified'): self.apply()
        self.assertEqual(b'original', (self.root/self.name).read_bytes())
        self.assertFalse(self.receipt.exists())

    def test_failed_receipt_write_rolls_back_all_applied_source(self):
        atomic_write = review.atomic_write
        def fail_receipt(path, *args):
            if path == self.receipt:
                raise OSError('disk failure')
            return atomic_write(path, *args)
        with patch.object(review, 'atomic_write', side_effect=fail_receipt):
            with self.assertRaises(OSError): self.apply()
        self.assertEqual(b'original', (self.root/self.name).read_bytes())
        self.assertFalse(self.receipt.exists())

    def test_unrelated_write_deletion_and_symlink_fail_before_apply(self):
        forbidden = self.snapshot/'owner_gateway/api.py'
        forbidden.parent.mkdir()
        forbidden.write_text('out of scope')
        with self.assertRaisesRegex(ValueError, 'outside'): self.apply()
        forbidden.unlink()
        (self.snapshot/self.name).unlink()
        with self.assertRaisesRegex(ValueError, 'deletes'): self.apply()
        (self.snapshot/self.name).symlink_to(self.root/self.name)
        with self.assertRaisesRegex(ValueError, 'symlink'): self.apply()
        self.assertEqual(b'original', (self.root/self.name).read_bytes())
