"""Record candidate README clips without changing the agent or environment.

Saves lossless returned frames and evaluator-only event logs, not GIFs.
Use a new output directory. These selected demonstrations are not benchmarks.
"""
import argparse
import hashlib
import importlib.metadata
import json
import multiprocessing as mp
from pathlib import Path

import crafter
import numpy as np

from crafter_symbolic import __version__
from crafter_symbolic.agent import Agent, ACTION_NAMES


def record(task):
    seed, directory = task
    env = crafter.Env(seed=seed, length=10000)
    if tuple(env.action_names) != ACTION_NAMES:
        raise RuntimeError('Unsupported action order')
    agent, reward = Agent('pocket'), 0.0
    rgb = env.reset()
    frames, actions, rows, achievements = [rgb.copy()], [], [], {}
    first_diamond = None
    for step in range(1, 10001):
        action = agent.act(rgb, reward)
        rgb, reward, done, info = env.step(action)
        frames.append(rgb.copy())
        actions.append(action)
        current = {k: int(v) for k, v in info['achievements'].items() if v}
        new = {k: v-achievements.get(k, 0) for k, v in current.items()
               if v > achievements.get(k, 0)}
        achievements = current
        rows.append({'step': step, 'action': ACTION_NAMES[action],
                     'inventory': {k: int(v) for k, v in info['inventory'].items()},
                     'achievement_changes': new})
        if first_diamond is None and current.get('collect_diamond'):
            first_diamond = step
        if done:
            break
    else:
        raise RuntimeError('Episode failed to terminate')
    array = np.stack(frames)
    summary = {'seed': seed, 'variant': 'pocket', 'steps': step,
               'first_diamond_step': first_diamond, 'achievements': achievements,
               'terminal': 'dead' if info['inventory']['health'] <= 0 else 'horizon',
               'action_sha256': hashlib.sha256(bytes(actions)).hexdigest(),
               'rgb_sha256': hashlib.sha256(array.tobytes()).hexdigest(),
               'package_version': __version__,
               'crafter_version': importlib.metadata.version('crafter'),
               'purpose': 'selected gameplay illustration; excluded from benchmarks'}
    base = Path(directory)/str(seed)
    with base.with_suffix('.npz').open('xb') as stream:
        np.savez_compressed(stream, rgb=array, actions=np.array(actions, dtype=np.uint8))
    with base.with_suffix('.json').open('x') as stream:
        json.dump({'summary': summary, 'steps': rows}, stream, indent=2)
        stream.write('\n')
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seeds', type=int, nargs='+', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=3)
    args = parser.parse_args()
    if args.workers < 1 or len(set(args.seeds)) != len(args.seeds):
        parser.error('Use positive workers and distinct seeds')
    if any(seed < 0 or seed >= 2**31 for seed in args.seeds):
        parser.error('Seeds must lie in [0, 2**31)')
    args.output.mkdir(parents=True, exist_ok=False)
    tasks = [(seed, str(args.output)) for seed in args.seeds]
    with mp.get_context('spawn').Pool(min(args.workers, len(tasks))) as pool:
        for result in pool.imap_unordered(record, tasks):
            print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
