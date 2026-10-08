"""Measure retained cutout inference memory in a fresh Linux process."""

from pathlib import Path
import json
import subprocess
import sys
import unittest


class CutoutMemoryTests(unittest.TestCase):
    @unittest.skipUnless(Path('/proc/self/status').exists(), 'Linux runtime memory probe')
    def test_preview_does_not_retain_large_inference_scratch_buffers(self):
        probe = '''
import gc
import json
from pathlib import Path
from validation_pipeline.template_assets import ASSET_ROOT
from validation_pipeline.template_cutout import cutout_png

def resident_kib():
    line = next(line for line in Path('/proc/self/status').read_text().splitlines()
                if line.startswith('VmRSS:'))
    return int(line.split()[1])

before = resident_kib()
source = (ASSET_ROOT / 'neutral_person_stock_v1-source.jpg').read_bytes()
result = cutout_png(source)
assert result.startswith(b'\\x89PNG\\r\\n\\x1a\\n')
gc.collect()
print(json.dumps({'retained_kib': resident_kib() - before}))
'''
        completed = subprocess.run(
            [sys.executable, '-c', probe], capture_output=True, text=True,
            check=True, timeout=180,
        )
        retained = json.loads(completed.stdout)['retained_kib']
        # The previous cached CPU arena retained >390 MiB after one preview.
        # Leave room for the model, NumPy, source/result cache and allocator
        # variation while protecting the 1 GiB runtime's idle reserve.
        self.assertLess(retained, 256 * 1024, f'Cutout retained {retained} KiB')
