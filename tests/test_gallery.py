"""Check the committed README clips and their recording metadata."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import unittest

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


class GalleryTests(unittest.TestCase):
    def test_readme_gallery_uses_one_image_paragraph_not_weighted_columns(self):
        readme = (ROOT/'README.md').read_text()
        image_paragraphs = [p for p in readme.split('\n\n') if '![' in p]
        self.assertEqual(len(image_paragraphs), 1)
        gallery = image_paragraphs[0]
        self.assertNotIn('|', gallery)
        self.assertNotIn('<table', gallery.lower())
        images = re.findall(r'!\[([^\]]+)\]\(([^)]+)\)', gallery)
        self.assertEqual([target for _, target in images], [
            'docs/assets/easy-diamond.gif',
            'docs/assets/long-diamond-hunt.gif',
            'docs/assets/shoreline-death.gif'])
        for (alt, target), step in zip(images, (67, 1862, 489)):
            self.assertIn(f'action {step}', alt)
            with Image.open(ROOT/target) as image:
                self.assertEqual(image.size, (256, 306))

    def test_assets_match_metadata(self):
        for name in ('easy-diamond', 'long-diamond-hunt', 'shoreline-death'):
            with self.subTest(clip=name):
                path = ROOT/'docs/assets'/f'{name}.gif'
                metadata = json.loads(path.with_suffix('.json').read_text())
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), metadata['gif_sha256'])
                self.assertEqual(path.stat().st_size, metadata['gif_bytes'])
                self.assertTrue(metadata['selected_example_not_benchmark'])
                steps = metadata['frame_steps']
                self.assertEqual(steps, sorted(set(steps)))
                self.assertEqual((steps[0], steps[-1]), (metadata['start'], metadata['end']))
                with Image.open(path) as image:
                    self.assertEqual(image.size, (256, 306))
                    self.assertEqual(image.info['loop'], 0)
                    self.assertEqual(image.n_frames, len(steps))
                    duration = 0
                    for i in range(image.n_frames):
                        image.seek(i)
                        image.load()
                        duration += image.info['duration']
                    self.assertEqual(duration, metadata['duration_ms'])
                summary = metadata['summary']
                if name == 'shoreline-death':
                    self.assertEqual(steps, list(range(summary['steps']+1)))
                    self.assertIsNone(summary['first_diamond_step'])
                    self.assertEqual(summary['terminal'], 'dead')
                    self.assertEqual(metadata['end'], summary['steps'])
                else:
                    self.assertEqual(metadata['end'], summary['first_diamond_step'])
                self.assertEqual(metadata['tail_actions_per_second'], 3)

    def test_timelapse_keeps_endpoints_and_final_actions(self):
        spec = importlib.util.spec_from_file_location('render_gallery', ROOT/'scripts/render_gallery.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        steps = module.selected_steps(0, 1862, 8, 40)
        self.assertEqual((steps[0], steps[-1]), (0, 1862))
        self.assertTrue(set(range(1822, 1863)).issubset(steps))
        self.assertEqual(steps, sorted(set(steps)))

    def test_timing_uses_action_gaps_and_switches_rate(self):
        spec = importlib.util.spec_from_file_location('render_gallery', ROOT/'scripts/render_gallery.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        steps = module.selected_steps(0, 1862, 4, 40)
        durations = module.frame_durations(steps, 48, 3, 1822)
        self.assertEqual(sum(durations), 54410)
        self.assertEqual((durations[0], durations[-1]), (700, 2500))
        switch = steps.index(1822)
        self.assertTrue(set(durations[switch:-1]).issubset({330, 340}))
        self.assertEqual(len(durations), len(steps))


if __name__ == '__main__':
    unittest.main()
