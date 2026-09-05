"""Offline input-boundary audit of an installed, unchanged release.

Recordings are loaded before installing guards. The agent receives only RGB
and deliberately varied rewards. No Crafter environment is imported or made.
This is a diagnostic regression check, not a hostile-code security sandbox.
"""
import argparse
import ast
import hashlib
import importlib
import json
import multiprocessing as mp
import os
from pathlib import Path
import sys

import numpy as np
from PIL import Image

from crafter_symbolic import Agent
from crafter_symbolic._policy import local_combat_pilot


def one_recording(path):
    path = Path(path)
    with np.load(path, allow_pickle=False) as data:
        frames, expected = data['rgb'].copy(), data['actions'].copy()
    metadata = json.loads(path.with_suffix('.json').read_text())['summary']
    assert 'crafter' not in sys.modules
    Image.init()
    agent = Agent()
    combined = Agent('combined')
    assert agent._controller.__class__.__name__ == 'ExpeditionAgent'
    flags = {n: getattr(agent._controller, n) for n in (
        'pocket_enabled', 'provision_enabled', 'excursions_enabled',
        'tour_enabled', 'food_distance', 'forge_return_enabled', 'combat_enabled')}
    assert flags == dict(pocket_enabled=True, provision_enabled=False,
                         excursions_enabled=False, tour_enabled=False,
                         food_distance=6, forge_return_enabled=True, combat_enabled=True)
    assets = agent._controller.decoder.asset_dir.resolve()
    events = []

    def guard(event, args):
        if event == 'open':
            target, mode, flags = args
            # A fresh/reset decoder is allowed immutable public PNG reads.
            allowed = isinstance(target, (str, bytes)) and not isinstance(target, int)
            if allowed:
                candidate = Path(os.fsdecode(target)).absolute()
                allowed = candidate.parent == assets and candidate.suffix == '.png'
            writing = (isinstance(mode, str) and any(c in mode for c in 'wa+')) or (
                isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT))
            if not allowed or writing:
                raise AssertionError(f'Unexpected file access during policy replay: {event}')
            events.append('public_png_read')
        elif event.startswith(('socket.', 'subprocess.', 'ctypes.')) or event in {
                'os.system', 'os.fork', 'os.posix_spawn', 'os.exec', 'os.spawn'}:
            raise AssertionError(f'External operation during policy replay: {event}')
        elif event == 'import' and args[0].split('.')[0] in {
                'crafter', 'socket', 'requests', 'torch', 'subprocess'}:
            raise AssertionError(f'Forbidden runtime import: {args[0]}')

    sys.addaudithook(guard)
    matched, prefix_matches = 0, 0
    first_diamond = metadata['first_diamond_step']
    prefix = first_diamond if first_diamond is not None else len(expected)
    for index, wanted in enumerate(expected):
        rgb = frames[index].copy()
        before = rgb.tobytes()
        actual = agent.act(rgb, 0.0)
        assert before == rgb.tobytes(), 'Policy mutated the input image'
        assert actual == int(wanted), (path.stem, index, actual, int(wanted))
        matched += 1
        if index < prefix:
            assert combined.act(rgb, (-999.0 if index % 2 else 999.0)) == actual
            prefix_matches += 1
    assert 'crafter' not in sys.modules

    # Reset after a whole episode, not merely the first action. Decoder caches
    # may persist, but map, position, goals and clocks must be fresh.
    agent.reset()
    assert agent.steps == 0 and agent._controller.position == (0, 0)
    assert not agent._controller.materials and agent._controller.first_saw_diamond is None
    reset_matches = 0
    for index, wanted in enumerate(expected):
        actual = agent.act(frames[index].copy(), float(index % 7)-3)
        assert actual == int(wanted), ('reset', path.stem, index, actual, int(wanted))
        reset_matches += 1
    assert 'crafter' not in sys.modules
    return {'recording': path.name, 'actions': len(expected), 'action_matches': matched,
            'reset_action_matches': reset_matches, 'combined_prefix_matches': prefix_matches,
            'zero_and_varied_rewards': True, 'crafter_imported': False,
            'public_asset_reads_after_guard': len(events),
            'action_sha256': hashlib.sha256(expected.tobytes()).hexdigest(),
            'flags': flags}


def source_checks():
    import crafter_symbolic
    root = Path(crafter_symbolic.__file__).parent
    paths = [root/'agent.py', *sorted((root/'_policy').glob('*.py'))]
    allowed = {'__future__', 'collections', 'dataclasses', 'heapq', 'math',
               'typing', 'numpy', 'PIL', 'importlib', 'pathlib', 'random', 'itertools'}
    forbidden_attrs = {'_world', '_player', 'semantic', 'player_pos', 'random_state',
                       'getstate', 'setstate', 'environ', 'getenv', '_getframe'}
    checks = []
    for path in paths:
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(n.name.split('.')[0] in allowed for n in node.names), path.name
            if isinstance(node, ast.ImportFrom) and node.level == 0:
                assert node.module.split('.')[0] in allowed, path.name
            if isinstance(node, ast.Attribute):
                assert node.attr not in forbidden_attrs, (path.name, node.attr)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in {'eval', 'exec', 'globals', 'locals', 'compile', '__import__'}
        checks.append({'file': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--record-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=3)
    args = parser.parse_args()
    sources = source_checks()
    files = sorted(args.record_dir.glob('*.npz'))
    assert files and not args.output.exists()
    with mp.get_context('spawn').Pool(min(args.workers, len(files)), maxtasksperchild=1) as pool:
        rows = []
        for row in pool.imap_unordered(one_recording, map(str, files)):
            rows.append(row)
            print(json.dumps(row), flush=True)
    result = {'kind': 'OFFLINE_BOUNDARY_AUDIT_NOT_BENCHMARK', 'sources': sources,
              'records': sorted(rows, key=lambda r:r['recording']),
              'actions_replayed': sum(r['actions'] for r in rows),
              'reset_actions_replayed': sum(r['reset_action_matches'] for r in rows),
              'combined_prefix_actions': sum(r['combined_prefix_matches'] for r in rows),
              'guard_scope': 'Python audit hook, no live environment import; not a hostile-code sandbox'}
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')


if __name__ == '__main__':
    main()
