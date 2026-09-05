# README gameplay clips

These are selected examples from six new recordings of the released `pocket`
agent, running stock Crafter 1.8.3. They are illustrations, not a new benchmark
sample. The recorded episodes continued until death; the two diamond clips
stop at collection. No agent rules were changed for these recordings.

| Clip | Seed | Actions shown | Playback |
|---|---:|---:|---|
| [Quick diamond](assets/easy-diamond.gif) | 205000138 | 0–67 | 25.2 seconds; 3 actions/sec |
| [Hard-earned diamond](assets/long-diamond-hunt.gif) | 205000123 | 0–1,862 | 54.4 seconds; 48 then 3 actions/sec |
| [Fatal shoreline fight](assets/shoreline-death.gif) | 205000002 | 0–489, full game | 58.9 seconds; 12 then 3 actions/sec |

## Why these three?

The quick run completes the resource and tool chain and collects diamond in
67 actions. Resources are close enough that it can finish before survival
becomes a major distraction.

The difficult run makes its iron pickaxe at action 90 but doesn't get diamond
until action 1,862. Before collection, it mines 87 stone, eats 9 cows and wakes
from sleep 17 times. Its health drops as low as 1 and recovers. This was the
longest successful diamond hunt among the six recordings, chosen from worlds
with late successes in the saved results. We haven't defined a measure that
would establish it as the most complex possible game.

The failed run ends in a fight along a narrow strip of shoreline, where water
and trees leave little room to move. It enters the final sequence at full
health and dies at action 489, without diamond. The GIF shows the whole game,
including the terminal frame with zero health; it is not merely a close call.

## What you see

The game area is the exact returned 64×64 RGB observation, including the HUD
and nighttime darkness, enlarged fourfold with nearest-neighbor sampling.
GIF palette conversion is the only color conversion. Labels are outside the
game image and are not inputs to the agent. No extra `env.render()` call is
made, since that can change Crafter's random state.

The quick run shows every action at 3 actions/sec. The long hunt is a timelapse
at 48 actions/sec, displaying every fourth action; its final 40 actions are
shown individually at 3 actions/sec. The failed game shows every action at
12 actions/sec, slowing to 3 for its final 60 actions. This keeps each GIF
under a minute while making the endings easier to follow.

The current actions/sec is shown above each game image. The first frame pauses
for 0.7 seconds and the last for 2.5 seconds. GIF timing is rounded to
centiseconds without accumulating speed drift. The step counter shows the
original action number, not the GIF frame number.

The files total about 13.3 MB. Each GIF has a JSON file alongside it with seed,
episode results, included frame numbers, playback duration and hashes of the
GIF, full action sequence and original RGB recording. `summary.achievements`
describes the full episode, not just the excerpt.
Crafter artwork is covered by its [MIT notice](assets/CRAFTER_LICENSE.md).

## Make your own

For an ordinary full-episode GIF, use the existing runner:

```bash
crafter-symbolic --seed 205000138 --record-dir runs/my-gifs
```

To make labeled excerpts like the README, run from the repository root after
installation. Recording saves lossless frames and event logs in the ignored
`runs/` folder. Evaluation information is only logged; the agent still gets
only RGB and the previous reward.

```bash
python scripts/record_gallery.py --seeds 205000138 205000123 205000002 --workers 3 --output runs/gallery
python scripts/render_gallery.py --input runs/gallery/205000138.npz --output runs/quick.gif --title 'Quick diamond' --end diamond --actions-per-second 3
python scripts/render_gallery.py --input runs/gallery/205000123.npz --output runs/hunt.gif --title 'The long diamond hunt' --end diamond --stride 4 --actions-per-second 48 --tail 40 --tail-actions-per-second 3
python scripts/render_gallery.py --input runs/gallery/205000002.npz --output runs/death.gif --title 'A fatal shoreline fight' --end death --actions-per-second 12 --tail 60 --tail-actions-per-second 3
```

Use fresh output paths. A seed does not guarantee an identical trajectory
across stock Crafter processes: object iteration order can change events.
Check the new recording's JSON before choosing clip ranges. The renderer
refuses `--end diamond` when that recording did not collect one.

The other three candidate seeds were 206000047, 205000234 and 205000041.
Only the two displayed successes collected diamond in this six-recording
batch. None of these results were added to the published benchmark totals.

[Back to README](../README.md)
