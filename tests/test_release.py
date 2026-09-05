import ast
import contextlib
import io
import importlib.util
import json
import math
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock

import crafter
import numpy as np

from crafter_symbolic import Agent, ACTION_NAMES
from crafter_symbolic._policy.crafter_rgb_decoder import CrafterRGBDecoder, ITEMS, daylight
from crafter_symbolic._policy.corrected_symbolic_agent import UNKNOWN_OBJECT
from crafter_symbolic._policy.visual_symbolic_observation import VisualSymbolicObservation
from crafter_symbolic.cli import main, run_episode
from crafter_symbolic.metrics import ACHIEVEMENTS, summarize
from crafter_symbolic.viewer import FrameViewer


class ReleaseTests(unittest.TestCase):
    def test_archive_check_rejects_nested_finder_metadata(self):
        root = Path(__file__).resolve().parents[1]
        spec = importlib.util.spec_from_file_location('verify_repository', root/'scripts/verify_repository.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.assert_no_finder_metadata(['package/agent.py', 'docs/README.md'])
        for name in ('.DS_Store', 'docs/assets/.DS_Store', 'package/._agent.py'):
            with self.subTest(path=name), self.assertRaises(AssertionError):
                module.assert_no_finder_metadata([name])
        self.assertIn('.DS_Store', (root/'.gitignore').read_text().splitlines())
        self.assertIn('global-exclude .DS_Store ._*', (root/'MANIFEST.in').read_text())

    def test_public_action_is_int_and_reset_is_fresh(self):
        rgb = crafter.Env(seed=71).reset()
        for variant in ('pocket', 'combined'):
            agent = Agent(variant)
            first = agent.act(rgb)
            self.assertIsInstance(first, int)
            self.assertIn(first, range(17))
            self.assertEqual(agent.steps, 1)
            agent.reset()
            self.assertEqual(agent.steps, 0)
            self.assertEqual(agent.act(rgb), first)

    def test_invalid_inputs_rejected(self):
        with self.assertRaises(ValueError):
            Agent('full')
        a = Agent()
        for rgb in ({'semantic': []}, np.zeros((63, 64, 3), np.uint8), np.zeros((64, 64, 3))):
            with self.assertRaises(ValueError):
                a.act(rgb)

    def test_stock_action_order(self):
        self.assertEqual(tuple(crafter.Env().action_names), ACTION_NAMES)

    def test_policy_sources_have_no_live_simulator_or_network_channel(self):
        import crafter_symbolic
        root = Path(crafter_symbolic.__file__).parent
        forbidden = {'_world', '_player', 'semantic', 'player_pos', '_random', 'random_state'}
        for path in [root/'agent.py', *(root/'_policy').glob('*.py')]:
            tree = ast.parse(path.read_text())
            attrs = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
            self.assertFalse(attrs & forbidden, path.name)
            for n in ast.walk(tree):
                if isinstance(n, ast.Import):
                    self.assertFalse({v.name.split('.')[0] for v in n.names} &
                                     {'crafter', 'requests', 'socket', 'torch', 'subprocess'}, path.name)
        self.assertFalse((root/'crafter_oracle_adapter.py').exists())

    def test_hud_all_digits_from_public_templates(self):
        decoder = CrafterRGBDecoder()
        for amount in range(10):
            rgb = np.zeros((64, 64, 3), np.uint8)
            for i, item in enumerate(ITEMS):
                y, x = 49+7*(i//9), 7*(i%9)
                rgb[y:y+7, x:x+7] = decoder._hud_templates[item][amount]
            self.assertEqual(decoder.decode_hud(rgb), {name: amount for name in ITEMS})

    def test_stock_daylight_materials_match_local_truth(self):
        # Simulator truth is a test oracle only, never an Agent input.
        env = crafter.Env(seed=104729)
        decoded = CrafterRGBDecoder().decode(env.reset(), step=0)
        center = tuple(int(x) for x in env._player.pos)
        expected = {}
        for dx in range(-4, 5):
            for dy in range(-3, 4):
                material, _ = env._world[(center[0]+dx, center[1]+dy)]
                expected[(dx, dy)] = material if material is not None else 'void'
        self.assertEqual(decoded.materials, expected)

    def test_night_abstention_preserves_hud_not_perfect_semantics(self):
        decoder = CrafterRGBDecoder()
        self.assertLess(daylight(180), .5)
        for seed in range(64):
            env = crafter.Env(seed=seed)
            env.reset()
            for _ in range(180):
                rgb, reward, done, info = env.step(0)
                if done:
                    break
            if done:
                continue
            decoded = decoder.decode(rgb, step=180, reward=reward,
                night_material_margin=float('inf'),
                night_object_absence_margin=float('inf'),
                night_object_presence_margin=float('inf'))
            self.assertEqual(decoded.materials, {})
            self.assertEqual(decoded.objects, {})
            self.assertEqual(decoded.object_absent, frozenset({(0, 0)}))
            self.assertEqual(decoded.inventory, info['inventory'])
            return
        self.fail('No stock fixture survived to the test night')

    def test_unknown_is_not_empty(self):
        controller = Agent()._controller
        inventory = {name: 0 for name in ITEMS}
        inventory.update(health=9, food=9, drink=9, energy=9)
        obs = VisualSymbolicObservation(materials={(0, 0): 'grass', (1, 0): 'grass'},
            objects={}, object_absent=frozenset({(0, 0)}), object_directions={},
            inventory=inventory, facing=(1, 0), sleeping=False)
        controller.act_visual(obs)
        self.assertEqual(controller.visible_objects[(1, 0)], UNKNOWN_OBJECT)
        self.assertNotIn((1, 0), controller.current_visible_cells)

    def test_visual_schema_rejects_contradiction_and_global_offsets(self):
        kw = dict(materials={}, objects={(1, 0): 'cow'}, object_absent=frozenset({(1, 0)}),
                  object_directions={}, inventory={}, facing=(1, 0), sleeping=False)
        with self.assertRaises(ValueError):
            VisualSymbolicObservation(**kw)
        kw.update(objects={}, object_absent=frozenset(), materials={(5, 0): 'diamond'})
        with self.assertRaises(ValueError):
            VisualSymbolicObservation(**kw)

    def test_pocket_and_combined_share_prediamond_actions(self):
        env = crafter.Env(seed=199000003, length=120)
        rgb, reward = env.reset(), 0.0
        a, b = Agent('pocket'), Agent('combined')
        for _ in range(120):
            x, y = a.act(rgb, reward), b.act(rgb, reward)
            self.assertEqual(x, y)
            rgb, reward, done, info = env.step(x)
            if done or info['achievements'].get('collect_diamond'):
                break

    def test_metrics_use_whole_profile_and_all_episode_cdf_denominator(self):
        rows = [{'achievements': {a: 1 for a in ACHIEVEMENTS}, 'first_diamond_step': 42, 'steps': 80},
                {'achievements': {}, 'first_diamond_step': None, 'steps': 90}]
        result = summarize(rows)
        self.assertAlmostEqual(result['crafter_score'], 50)
        self.assertEqual(result['unconditional_diamond_percent_by_step']['100'], 50)
        self.assertEqual(result['first_diamond_steps_among_successes']['median'], 42)
        with self.assertRaises(ValueError):
            summarize([])

    def test_runner_never_rerenders_and_never_passes_info_to_agent(self):
        rgb = np.zeros((64, 64, 3), np.uint8)
        class Environment:
            action_names = ACTION_NAMES
            def __init__(self, **kwargs): pass
            def reset(self): return rgb
            def render(self): raise AssertionError('extra render')
            def step(self, action):
                return rgb, 0., True, {'achievements': {}, 'inventory': {'health': 0},
                    'semantic': object(), 'player_pos': object()}
        class Policy:
            def __init__(self, variant): pass
            def act(self, frame, reward):
                if frame is not rgb: raise AssertionError('frame replaced')
                return 0
        with patch('crafter_symbolic.cli.crafter.Env', Environment), patch('crafter_symbolic.cli.Agent', Policy):
            row = run_episode((0, 0, 10000, 'pocket', None))
        self.assertEqual(row['terminal'], 'dead')
        self.assertEqual(row['steps'], 1)

    def test_stock_runner_and_gif(self):
        with tempfile.TemporaryDirectory() as tmp:
            row = run_episode((0, 73, 3, 'pocket', tmp), fps=20)
            self.assertEqual(row['steps'], 3)
            self.assertEqual(row['terminal'], 'horizon')
            self.assertTrue((Path(tmp)/row['recording']).is_file())
            from PIL import Image, ImageSequence
            with Image.open(Path(tmp)/row['recording']) as gif:
                self.assertEqual(gif.size, (64, 64))
                self.assertEqual(sum(frame.info['duration'] for frame in ImageSequence.Iterator(gif)), 200)

    def test_headless_does_not_initialize_viewer(self):
        with patch('crafter_symbolic.cli.FrameViewer') as viewer:
            run_episode((0, 73, 1, 'pocket', None))
            viewer.assert_not_called()

    def test_viewer_gets_only_returned_frames_and_closes(self):
        first = crafter.Env(seed=73).reset()
        last = first.copy()
        class Environment:
            action_names = ACTION_NAMES
            def __init__(self, **kwargs): pass
            def reset(self): return first
            def render(self): raise AssertionError('extra render')
            def step(self, action):
                return last, 0., True, {'achievements': {}, 'inventory': {'health': 0}}
        with patch('crafter_symbolic.cli.crafter.Env', Environment), patch('crafter_symbolic.cli.FrameViewer') as factory:
            viewer = factory.return_value
            run_episode((0, 73, 10, 'pocket', None), show=True)
            self.assertIs(viewer.show.call_args_list[0].args[0], first)
            self.assertIs(viewer.show.call_args_list[1].args[0], last)
            self.assertEqual(viewer.show.call_args_list[1].kwargs['step'], 1)
            viewer.close.assert_called_once()

    def test_viewer_interrupt_closes_and_does_not_save_incomplete_gif(self):
        with tempfile.TemporaryDirectory() as tmp, patch('crafter_symbolic.cli.FrameViewer') as factory:
            factory.return_value.show.side_effect = KeyboardInterrupt
            with self.assertRaises(KeyboardInterrupt):
                run_episode((0, 73, 10, 'pocket', tmp), show=True)
            factory.return_value.close.assert_called_once()
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_cli_viewer_worker_and_rate_validation(self):
        for args in (['--show', '--workers', '2'], ['--fps', '61'], ['--scale', '17']):
            with patch('crafter_symbolic.cli.run_episode') as run:
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    main(args)
                run.assert_not_called()

    @unittest.skipUnless(importlib.util.find_spec('pygame'), 'optional viewer extra not installed')
    def test_viewer_preserves_pixel_orientation_and_pause_escape(self):
        # Offscreen SDL driver: no desktop window in automated tests.
        with patch.dict(os.environ, {'SDL_VIDEODRIVER': 'dummy'}):
            viewer = FrameViewer('test', fps=60, scale=2)
            try:
                rgb = np.zeros((64, 64, 3), np.uint8)
                rgb[1, 2] = (17, 61, 203)
                original = rgb.copy()
                viewer.show(rgb)
                self.assertEqual(tuple(viewer.screen.get_at((4, 2)))[:3], (17, 61, 203))
                np.testing.assert_array_equal(rgb, original)
                pg = viewer.pg
                pg.event.post(pg.event.Event(pg.KEYDOWN, key=pg.K_SPACE))
                # The pause loop must not advance until a second Space.
                viewer.clock = Mock()
                viewer.clock.tick.side_effect = lambda rate: (
                    pg.event.post(pg.event.Event(pg.KEYDOWN, key=pg.K_SPACE))
                    if viewer.paused else None)
                viewer.show(rgb)
                self.assertEqual(viewer.clock.tick.call_count, 2)
                self.assertFalse(viewer.paused)
                pg.event.post(pg.event.Event(pg.KEYDOWN, key=pg.K_ESCAPE))
                with self.assertRaises(KeyboardInterrupt):
                    viewer.show(rgb)
            finally:
                viewer.close()
            self.assertFalse(viewer.pg.display.get_init())

    def test_cli_rejects_output_journal_collision_before_running(self):
        with patch('crafter_symbolic.cli.run_episode') as run:
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main(['--output', 'bad.jsonl'])
            run.assert_not_called()

    def test_cli_preserves_existing_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'existing.json'
            path.touch()
            with patch('crafter_symbolic.cli.run_episode') as run:
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    main(['--output', str(path)])
                run.assert_not_called()
            self.assertEqual(path.read_bytes(), b'')


if __name__ == '__main__':
    unittest.main()
