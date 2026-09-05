"""Stock-Crafter runner. Evaluation info is never passed to the policy."""
import argparse
from functools import partial
import hashlib
import importlib.metadata
import json
import multiprocessing as mp
from pathlib import Path
import sys
import time

import crafter

from .agent import Agent, ACTION_NAMES
from .metrics import summarize
from . import __version__
from .viewer import FrameViewer, ViewerUnavailable


def run_episode(task, *, show=False, fps=10, scale=8):
    index, seed, length, variant, record_dir = task
    env = crafter.Env(seed=seed, length=length)
    if tuple(env.action_names) != ACTION_NAMES:
        raise RuntimeError('Unsupported Crafter action names/order')
    rgb = env.reset()
    agent, reward = Agent(variant), 0.0
    first_diamond, action_hash = None, hashlib.sha256()
    frames = [rgb.copy()] if record_dir else None
    viewer = None
    started = time.perf_counter()
    try:
        if show:
            viewer = FrameViewer(f'Crafter — {variant} — seed {seed}', fps=fps, scale=scale)
            viewer.show(rgb)
        for step in range(1, length+1):
            # This is the only policy call. No info/world/position/seed inputs.
            action = agent.act(rgb, reward)
            action_hash.update(bytes([action]))
            rgb, reward, done, info = env.step(action)
            if frames is not None:
                frames.append(rgb.copy())
            if first_diamond is None and info['achievements'].get('collect_diamond', 0):
                first_diamond = step
            if viewer is not None:
                viewer.show(rgb, step=step, action=ACTION_NAMES[action], done=done)
            if done:
                break
        else:
            raise RuntimeError('Crafter did not terminate at its configured horizon')
        record = None
        if frames is not None:
            import imageio.v2 as imageio
            path = Path(record_dir)/f'{variant}_{seed}.gif'
            with path.open('xb') as stream:
                imageio.mimsave(stream, frames, format='GIF', duration=1000/fps, loop=0)
            record = path.name
        return {
            'episode': index, 'seed': seed, 'variant': variant, 'steps': step,
            'first_diamond_step': first_diamond,
            'achievements': {k: int(v) for k, v in info['achievements'].items() if v},
            'terminal': 'dead' if info['inventory']['health'] <= 0 else 'horizon',
            'action_sha256': action_hash.hexdigest(), 'recording': record,
            'wall_time_seconds': time.perf_counter()-started,
        }
    finally:
        if viewer is not None:
            viewer.close()
        close = getattr(env, 'close', None)
        if close is not None:
            close()


def positive(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError('must be positive')
    return number


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--episodes', type=positive, default=1)
    parser.add_argument('--seed', type=int, default=0, help='first environment seed; never given to Agent')
    parser.add_argument('--workers', type=positive, default=1)
    parser.add_argument('--length', type=positive, default=10000, help='benchmark=10000; shorter runs are smoke tests')
    parser.add_argument('--variant', choices=('pocket', 'combined'), default='pocket')
    parser.add_argument('--output', type=Path, help='new JSON file; a partial JSONL journal is preserved on interruption')
    parser.add_argument('--record-dir', type=Path, help='new directory for GIFs of the exact returned frames')
    parser.add_argument('--show', action='store_true', help='opt-in live window; needs viewer extra and --workers 1')
    parser.add_argument('--fps', type=positive, default=10, help='live/GIF playback frames per second (1..60); no headless throttling')
    parser.add_argument('--scale', type=positive, default=8, help='live window pixel enlargement (1..16); agent/GIF stay 64x64')
    args = parser.parse_args(argv)
    if args.length > 10000 or args.seed < 0 or args.seed+args.episodes > 2**31:
        parser.error('length must be <=10000 and seeds must lie in [0,2**31)')
    if args.output and args.output.suffix != '.json':
        parser.error('--output must end in .json; its journal uses .jsonl')
    if args.fps > 60 or args.scale > 16:
        parser.error('--fps must be <=60 and --scale must be <=16')
    if args.show and args.workers != 1:
        parser.error('--show requires --workers 1; headless GIF recording supports multiple workers')
    if importlib.metadata.version('crafter') != '1.8.3':
        parser.error('This release is verified for crafter==1.8.3')
    journal = args.output.with_suffix('.jsonl') if args.output else None
    if args.output and (args.output.exists() or journal.exists()):
        parser.error('Output/journal already exists; choose a fresh filename')
    if args.record_dir:
        args.record_dir.mkdir(parents=True, exist_ok=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
    tasks = [(i, args.seed+i, args.length, args.variant,
              str(args.record_dir) if args.record_dir else None) for i in range(args.episodes)]
    rows, started = [], time.perf_counter()
    runner = partial(run_episode, show=args.show, fps=args.fps, scale=args.scale)
    stream = journal.open('x') if journal else None
    try:
        if args.workers == 1:
            for row in map(runner, tasks):
                rows.append(row)
                if stream:
                    stream.write(json.dumps(row)+'\n'); stream.flush()
                print(f'Completed {len(rows)}/{len(tasks)} episodes', file=sys.stderr, flush=True)
        else:
            with mp.get_context('spawn').Pool(min(args.workers, args.episodes)) as pool:
                for row in pool.imap_unordered(runner, tasks):
                    rows.append(row)
                    if stream:
                        stream.write(json.dumps(row)+'\n'); stream.flush()
                    print(f'Completed {len(rows)}/{len(tasks)} episodes', file=sys.stderr, flush=True)
    except KeyboardInterrupt:
        parser.exit(130, 'Stopped. Completed episode journals/GIFs are preserved; the current episode is incomplete.\n')
    except ViewerUnavailable as exc:
        parser.exit(2, f'{exc}\n')
    finally:
        if stream:
            stream.close()
    rows.sort(key=lambda r: r['episode'])
    result = {
        'package_version': __version__, 'environment': 'stock crafter.Env 1.8.3',
        'display': {'show': args.show, 'fps': args.fps, 'scale': args.scale},
        'observation_contract': 'exact returned RGB and previous reward only',
        'variant': args.variant, 'length': args.length,
        'benchmark_horizon': args.length == 10000,
        'dependencies': {n: importlib.metadata.version(n) for n in
                         ('crafter', 'numpy', 'Pillow', 'imageio', 'opensimplex', 'ruamel.yaml')},
        'summary': summarize(rows), 'episodes': rows,
        'wall_time_seconds': time.perf_counter()-started,
    }
    if args.output:
        with args.output.open('x') as stream:
            json.dump(result, stream, indent=2); stream.write('\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
