"""Turn a saved gallery recording into a small, labeled gameplay GIF.

The game image is only enlarged with nearest-neighbor sampling and GIF palette
conversion. Labels sit outside it. No hidden-state imagery or extra rendering.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


def selected_steps(start, end, stride, tail):
    steps = set(range(start, end+1, stride))
    steps.update(range(max(start, end-tail), end+1))
    steps.update((start, end))
    return sorted(steps)


def frame_durations(steps, rate, tail_rate, slow_start):
    # Accumulate exact times before rounding to GIF centiseconds. This keeps
    # 3 actions/s at 3 on average instead of rounding every delay to 330 ms.
    elapsed, rounded, durations = 0.0, 0, []
    for left, right in zip(steps, steps[1:]):
        speed = tail_rate if left >= slow_start else rate
        elapsed += 1000*(right-left)/speed
        boundary = 10*round(elapsed/10)
        durations.append(boundary-rounded)
        rounded = boundary
    durations.append(2500)
    if len(durations) > 1:
        durations[0] = 700
    return durations


def make_frame(rgb, title, step, end, row, diamond, terminal, rate):
    canvas = Image.new('RGB', (256, 306), '#121820')
    canvas.paste(Image.fromarray(rgb).resize((256, 256), Image.Resampling.NEAREST), (0, 34))
    draw, font = ImageDraw.Draw(canvas), ImageFont.load_default()
    draw.text((8, 4), title, font=font, fill='#f4f4ef')
    speed = f'{rate:g} actions/s'
    draw.text((8, 19), f'Step {step:,} / {end:,}  |  {speed}', font=font, fill='#aab5c0')
    if diamond is not None and step >= diamond:
        label, color = 'DIAMOND COLLECTED', '#7ee7ec'
    elif row and row['inventory']['health'] == 0 and terminal == 'dead':
        label, color = 'DIED BEFORE FINDING DIAMOND', '#f1a291'
    else:
        label = row['action'].replace('_', ' ') if row else 'Start'
        changes = row.get('achievement_changes', {}) if row else {}
        if changes:
            label = next(iter(changes)).replace('_', ' ')
        color = '#cdd6df'
    draw.text((8, 293), label, font=font, fill=color)
    return canvas


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True, help='Recorded .npz file')
    parser.add_argument('--output', type=Path, required=True, help='New .gif file')
    parser.add_argument('--title', required=True)
    parser.add_argument('--start', type=int, default=0)
    parser.add_argument('--end', default='diamond', help='diamond, death, or action number')
    parser.add_argument('--stride', type=int, default=1)
    parser.add_argument('--tail', type=int, default=40, help='Show every final action')
    parser.add_argument('--actions-per-second', type=float, default=3,
                        help='Playback rate in original game actions per second')
    parser.add_argument('--tail-actions-per-second', type=float,
                        help='Optional slower rate for the final --tail actions')
    args = parser.parse_args()
    metadata = json.loads(args.input.with_suffix('.json').read_text())
    summary, rows = metadata['summary'], metadata['steps']
    if args.end == 'diamond':
        end = summary['first_diamond_step']
        if end is None:
            parser.error('This recording contains no diamond')
    elif args.end == 'death':
        if summary['terminal'] != 'dead':
            parser.error('This recording does not end in death')
        end = summary['steps']
    else:
        end = int(args.end)
    if args.stride < 1 or args.tail < 0 or not 0 <= args.start <= end <= summary['steps']:
        parser.error('Invalid clip range, stride or tail')
    rate = args.actions_per_second
    tail_rate = args.tail_actions_per_second if args.tail_actions_per_second is not None else rate
    if not 0 < rate <= 50*args.stride or not 0 < tail_rate <= 50:
        parser.error('Rates must be positive and keep displayed frames at 50 fps or less')
    if args.output.suffix.lower() != '.gif' or len(args.title) > 35:
        parser.error('Use a .gif output and a title of at most 35 characters')
    manifest = args.output.with_suffix('.json')
    if args.output.exists() or manifest.exists():
        parser.error('Output exists; choose a fresh filename')
    with np.load(args.input, allow_pickle=False) as data:
        rgb, actions = data['rgb'], data['actions']
    assert rgb.shape == (summary['steps']+1, 64, 64, 3) and rgb.dtype == np.uint8
    assert hashlib.sha256(rgb.tobytes()).hexdigest() == summary['rgb_sha256']
    assert hashlib.sha256(actions.tobytes()).hexdigest() == summary['action_sha256']
    steps = selected_steps(args.start, end, args.stride, args.tail)
    slow_start = max(args.start, end-args.tail)
    images = [make_frame(rgb[i], args.title, i, end, rows[i-1] if i else None,
                         summary['first_diamond_step'], summary['terminal'],
                         tail_rate if i >= slow_start else rate)
              for i in steps]
    durations = frame_durations(steps, rate, tail_rate, slow_start)
    if any(duration < 20 for duration in durations):
        parser.error('Some frame gaps are too short for reliable GIF playback; reduce the rate')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('xb') as stream:
        images[0].save(stream, format='GIF', save_all=True, append_images=images[1:],
                       duration=durations, loop=0, optimize=True, disposal=1)
    result = {'summary': summary, 'title': args.title, 'start': args.start, 'end': end,
              'stride': args.stride, 'tail': args.tail,
              'actions_per_second': rate, 'tail_actions_per_second': tail_rate,
              'frame_steps': steps,
              'duration_ms': sum(durations), 'gif_bytes': args.output.stat().st_size,
              'gif_sha256': hashlib.sha256(args.output.read_bytes()).hexdigest(),
              'presentation': 'Exact returned RGB, 4x nearest-neighbor enlargement, '
                              'GIF palette conversion; labels outside the image.',
              'selected_example_not_benchmark': True}
    with manifest.open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'frame_steps'}, indent=2))


if __name__ == '__main__':
    main()
