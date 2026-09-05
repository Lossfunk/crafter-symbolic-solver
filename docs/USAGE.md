# Complete usage and reference

[Back to the short README](../README.md). Run commands from the repository root.

**A diamond-first, RGB-only symbolic agent for Crafter.**

Watch an autonomous agent gather resources, craft tools, defend itself, explore
for diamond, and then pursue the remaining achievements. Everything runs locally
on the CPU: no training, neural weights, GPU, API key, or service is required.

The agent receives the exact **64×64 RGB observation** and previous reward,
maintains episode-local symbolic memory, and returns **one of 17 integer
actions**. It plays [Danijar Hafner's original Crafter](https://github.com/danijar/crafter)
without modifying the environment.

The recommended `pocket` policy achieved **69.98 Crafter score and 55.47%
diamond success (213/384 fresh episodes)** under a 10,000-action episode limit.
These are measured results, not a guarantee or a claim of optimality.

[Quick start](#quick-start) · [Watch and record](#watch-and-record) ·
[Python API](#python-api) · [Results](#results-and-interpretation) ·
[Troubleshooting](#troubleshooting) · [Full research audit](AUDIT.md)

## Why we built this

The starting question was: **how far can Crafter score—and especially the
probability of collecting diamond—be pushed within Crafter's 10,000-step
episode horizon?** Not how quickly an agent can learn, but how reliably it can
succeed in a new game once built, however much preparation went into it.

We used a symbolic heuristics solver as an inspectable system to iterate on:
reason about the game's dependencies, examine failures, test substantial changes,
and evaluate frozen candidates on fresh episodes. Diamond success came first;
broader achievement coverage followed, with faster diamond acquisition a
secondary objective that should not sacrifice success probability. Exploration,
survival, memory and resource planning all had to work together.

It turns out this approach goes a long way: roughly **70 Crafter score and
diamond in more than half of fresh episodes**, using the local RGB view and
episode-local memory. That is evidence of substantial attainable capability,
not a mathematical upper bound or proof that the remaining failures are
unavoidable. The release makes that result runnable and its limitations visible.

## What this project is

Crafter is a small survival world with a substantial planning problem: finding
diamond requires a chain of resources and tools while food, water, sleep and
enemies compete for attention.

The controller is more than a fixed action script. It has resumable tasks,
relative-map exploration, remembered landmarks, crafting plans, necessity
management, shelter behavior and narrowly gated local combat lookahead.
It decides independently throughout each episode; there is no human or language
model choosing actions during play.

Useful ways to interact with it:

- Watch an episode in a live window, or save it as a GIF.
- Run CPU-parallel batches and inspect all 22 achievement success rates.
- Embed `Agent.act()` in your own stock-Crafter loop.
- Study a transparent symbolic baseline, including its failed experiments and
  observation-contract corrections.

This is an **external-knowledge agent**: public textures and game mechanics are
hand-coded priors. It is not a learned agent entered under the paper's
one-million-interaction RL training budget. It is also not a neural replica;
the separate imitation-learning work remains unfinished and is not included.

## Quick start

Download or clone this repository, open a terminal in its root, and use
**Python 3.11** for the tested setup. The package declares Python 3.11 or newer;
other Python versions are not yet verified.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install .

# One complete episode, headless. Results are printed as JSON.
crafter-symbolic --seed 0
```

In Windows PowerShell, use `py -3.11 -m venv .venv` and
`.venv\Scripts\Activate.ps1` for the first two commands. Windows is not
locally verified.

Installation automatically installs `crafter==1.8.3` and the runtime
dependencies if needed. No separate Crafter checkout, Gym installation or
model download is required. Install from this checkout; a PyPI publication of
this agent is not assumed.

For the exact dependency versions used in verification:

```bash
python -m pip install -r requirements.lock .
```

The default run lasts until death or **10,000 environment actions**. It
continues after collecting diamond to pursue other achievements. A seed chooses
the environment initialization; it is never supplied to the agent.

If you only want to check installation:

```bash
python -m crafter_symbolic --length 20
```

Short runs are labeled `benchmark_horizon: false` and should not be compared
with full-episode scores.

## Watch and record

Both viewing and recording are **off by default**. No window opens and no GIF
is saved unless you request one.

### Watch the agent live

Install the optional viewer once:

```bash
python -m pip install ".[viewer]"
crafter-symbolic --show --seed 0
```

The window shows the agent's local view, including its inventory and nighttime
darkness. It defaults to 512×512: a nearest-neighbor enlargement of the original
pixels, not a higher-resolution or expanded observation.

- **Space:** pause or resume.
- **Escape / close window:** stop the run.
- `--fps 20`: change playback speed (default 10).
- `--scale 4`: use a 256×256 window (default scale 8).

The agent still controls every game action; keyboard input only controls the
viewer. Live viewing requires `--workers 1`.

### Save a GIF

GIF recording does not need the optional viewer or a desktop display:

```bash
crafter-symbolic --seed 0 --record-dir runs/gifs
```

This writes `runs/gifs/pocket_0.gif` when the episode completes.
For both live viewing and recording:

```bash
crafter-symbolic --show --seed 0 --fps 20 --record-dir runs/watch-and-save --output runs/watch-and-save.json
```

Use a **new directory and output filename** each time. The runner deliberately
refuses to overwrite existing data.

GIFs contain the returned 64×64 frames with the format's palette conversion.
`--scale` affects only the live window. GIF timing has centisecond precision;
`--fps` changes playback timing, not the number of environment actions.
Headless GIF generation is not slowed to playback speed.

Neither viewing nor recording makes an extra `env.render()` call. This
matters because Crafter's nighttime rendering consumes randomness.

On interruption, completed GIFs and completed journal rows remain. The current
unfinished episode is not saved as a completed GIF or benchmark result.
Recordings retain frames in memory, so use a modest worker count for video
batches.

## Run a batch and inspect results

```bash
# Full episodes on independent CPU workers.
crafter-symbolic --episodes 100 --workers 4 --seed 1000 --output runs/evaluation.json

# Optional GIF for every completed episode; keep the batch small initially.
crafter-symbolic --episodes 4 --workers 2 --seed 2000 --record-dir runs/batch-gifs --output runs/batch.json
```

`--seed 1000 --episodes 100` uses environment seeds 1000 through 1099.
Each episode starts with a fresh controller and no cross-episode memory.

The output has two levels:

| Output field | Meaning |
|---|---|
| `summary.crafter_score` | Geometric aggregate of all 22 achievement success rates |
| `summary.diamond_percent` | Percentage of complete episodes collecting diamond |
| `summary.achievement_percent` | Whole-episode success percentage for every achievement |
| `summary.first_diamond_steps_among_successes` | Minimum, median and maximum first-diamond action among successes only |
| `summary.unconditional_diamond_percent_by_step` | Diamond completion curve keeping failures in the denominator |
| `episodes` | Per-episode seed, actions taken, achievements, terminal reason and action hash |
| `dependencies`, `package_version`, `length` | Runtime/protocol metadata for interpreting the run |

For example, inspect a saved summary in Python:

```python
import json

with open("runs/evaluation.json") as stream:
    result = json.load(stream)

print(result["summary"]["crafter_score"])
print(result["summary"]["diamond_percent"])
print(result["summary"]["achievement_percent"])
```

With `--output`, completed episodes are also appended to a neighboring
`.jsonl` journal as the run proceeds. The final JSON is written only when the
whole requested batch finishes. The journal is recovery evidence, **not an
automatic resume mechanism**. Do not treat a stopped batch as a complete one.

Progress goes to stderr; the final JSON is also printed to stdout. Simulation
information is read by the evaluator for reporting, never passed into the
policy. An action hash helps compare recorded action sequences, but the same
seed is not a guarantee of bitwise-identical stock trajectories across processes
or runtime configurations.

## Command-line reference

`crafter-symbolic --help` and `python -m crafter_symbolic --help` are equivalent.

| Option | Default | Description |
|---|---|---|
| `--episodes N` | `1` | Number of episodes; positive integer |
| `--seed N` | `0` | First environment seed; the entire batch must stay below 2³¹ |
| `--workers N` | `1` | Independent CPU worker processes |
| `--length N` | `10000` | Maximum actions per episode, from 1 to 10000 |
| `--variant NAME` | `pocket` | Fixed `pocket` or `combined` controller |
| `--output PATH` | none | New `.json` file and neighboring `.jsonl` journal |
| `--record-dir PATH` | none | New directory for per-episode GIFs |
| `--show` | off | Open the optional live viewer; one worker only |
| `--fps N` | `10` | Live/GIF playback speed, from 1 to 60 |
| `--scale N` | `8` | Live-window pixel enlargement, from 1 to 16 |

## Python API

```python
import crafter
from crafter_symbolic import Agent, ACTION_NAMES

env = crafter.Env(seed=0, length=10000)
rgb, reward = env.reset(), 0.0
agent = Agent()  # equivalent to Agent(variant="pocket")

while True:
    action = agent.act(rgb, reward)  # Python int, 0..16
    # ACTION_NAMES[action] is its readable name.
    rgb, reward, done, info = env.step(action)
    if done:
        print(info["achievements"])  # reporting only
        break
```

The public interface is deliberately small:

| API | Contract |
|---|---|
| `Agent(variant="pocket")` | Construct a fixed controller with fresh episode memory |
| `agent.act(rgb, reward=0.0)` | Exact `numpy.uint8` array, shape `(64, 64, 3)`, plus previous transition reward; returns one integer action |
| `agent.reset()` | Clear episode memory while keeping the chosen variant |
| `agent.steps` | Number of observations/actions processed since reset |
| `ACTION_NAMES[action]` | Map the integer to Crafter's readable action name |

Use a new agent or call `reset()` at **every** environment reset. Call
`act()` once per returned observation, beginning with the reset frame, and
execute its proposed action before calling it again. Pass the previous
transition reward; the reset frame uses 0.0.

Do not feed `info`, semantic debug maps, private player fields, frame stacks,
resized images or additional rendered observations to the agent. Do not override
its actions or skip frames: its memory assumes the proposed action was executed.
This autonomous interface is not an action-override/DAgger training interface.

The modules under `_policy/` are internal implementation details, not a stable
public API. See [examples/play.py](../examples/play.py) for a complete minimal
program and [architecture](ARCHITECTURE.md) for the controller's internals.

## How it works

The hand-built perception front end matches the received pixels against
Crafter's public textures and rendering rules. It reads the installed assets,
not a live simulator. At night, ambiguous material/object evidence becomes
**unknown**, not a perfect label or a declaration of empty space.

The controller maintains a relative map, visit counts, resource and shelter
landmarks, recently recognized creatures, necessity estimates and task stages.
These memories are built from legal observations and reset each episode.
There is no initial global map, absolute player coordinate, game RNG access or
seed-conditioned expert selection.

Its main task priorities are survival and tactical handling, prerequisite
collection/crafting, returning to known diamond with an iron pickaxe, frontier
exploration, and then remaining achievements after diamond. A limited local
combat model considers short alternative continuations; it is approximate
planning, not a clone of the hidden environment or a safety guarantee.

`pocket` adds natural protected-crop handling **after diamond** to the
`combined` reference. Its pre-diamond decision law is unchanged. This is why
it is the practical default for broader achievements, rather than a seed oracle
choosing among personalities. Rejected experimental branches are not enabled.

## Results and interpretation

Completed fresh stock batches of the frozen policies:

| Policy | Episodes | Diamond successes | Diamond rate | Crafter score |
|---|---:|---:|---:|---:|
| `pocket` (recommended) | 384 | 213 | 55.47% | 69.98 |
| `combined` (reference) | 640 | 368 | 57.50% | 68.73 |

These are **different world cohorts**. The pooled difference is not a causal
comparison between policies. Pocket's diamond-rate Wilson 95% interval is
50.47–60.36%; its Score bootstrap interval is 67.30–72.43. Its first diamond
arrived at a median 410 actions **among successful episodes**.

Crafter Score is computed from the percentage p_i of episodes achieving each
of 22 achievements:

`Score = exp(mean(log(1 + p_i))) - 1`

It is not average episode reward or mean number of achievements. Pool episode
achievement counts before recomputing Score; do not average batch Scores.

The [benchmark report](BENCHMARKS.md) includes all 22 rates, confidence
intervals, fresh versus development comparisons, an unconditional speed curve
and the official human reference. Human comparisons are descriptive, not
matched comparisons of training budget or prior knowledge. Nothing here claims
a controlled “superhuman” result or the optimal achievable diamond rate.

[evidence/benchmarks.json](../evidence/benchmarks.json) ships 2,192 completed
episode summaries across the retained benchmark/comparison batches. That is
not the default policy's sample size. Recompute its reported point estimates
and verify frozen policy hashes without access to the original lab:

```bash
python scripts/verify_evidence.py
```

### Human and literature context

For this project's question, **training length is not a cutoff**: we want the
strongest finished agents, not just the original 1M-training-step leaderboard.
The following are selected published references checked on **2026-09-05**,
not a leaderboard or matched evaluation. We do not claim state-of-the-art
performance or superiority over humans or other agents.

| Agent / reference | Crafter score | Diamond episodes | Evaluation setting |
|---|---:|---:|---|
| This release: `pocket` | 69.98 | 55.47% | Stock Crafter; 64×64 RGB; 10k limit |
| [Human experts](https://arxiv.org/abs/2109.06780v2) | 50.5 ± 6.8 | 12% | Original Crafter; 100 games; 10k limit |
| [EMERALD](https://proceedings.mlr.press/v267/burchi25a.html) | 58.1 | 0.5% | Crafter; 64×64 RGB; 10k evaluation limit |
| [C-VPT (large)](https://arxiv.org/html/2508.13530v1) | 61.4 ± 4.7 | ≈13%* | Reported Crafter protocol; 144×144 RGB |

*C-VPT's diamond rate is an approximate reading of Figure 11, not a tabulated
number. Its paper states the standard Crafter protocol; exact equivalence to
our installed environment was not established. Human Score is the paper's
group-averaged result; pooling its 100 games gives **52.05** instead. Reported
error bars and our confidence intervals use different aggregation procedures.

Higher results also exist in **related, non-matched settings**:

- [CrafterDojo's symbolic-input expert](https://arxiv.org/html/2508.13530v1):
  **97.5 score / 71% diamond**, with 10k-step Craftax-Classic demonstration
  episodes. This is not the pixel-based C-VPT policy.
- [SCALAR](https://arxiv.org/html/2603.09036v1): **88.2% diamond** in
  10k-step Craftax-Classic with symbolic input and guaranteed diamond presence;
  a standard all-22 Crafter score is not provided alongside that result.

Here, symbolic input means structured game facts supplied directly; our agent
instead derives its symbols from RGB. Craftax-Classic is a reimplementation,
not the identical stock game, so the same 10,000 steps per episode do not make
the tests equivalent. The higher results remain relevant evidence of capability;
we have not isolated policy, input and world contributions to the difference.
Training budget, observation access, world generation and episode horizon must
be distinguished. The
[literature comparison](LITERATURE_COMPARISON.md) records source tables,
training context, horizon checks and exclusions.

## Limitations and provenance

- Supported target: stock `crafter==1.8.3`, default assets, 64×64 world and
  64×64 RGB output, with a 9×7 world crop plus HUD. Modified renderers,
  action repeats and alternate wrapper APIs are not verified.
- Public mechanics/textures are strong external knowledge. This is not a
  one-million-step learning-budget result.
- Nighttime perception abstains under ambiguity. Finite held-out validation
  observed no errors among accepted labels, but does not prove error-free
  decoding for every possible frame.
- Survival is not solved: every episode in the two pooled release-policy
  cohorts ended in death before 10,000 actions.
- Historical release 1.0 used privileged nighttime semantic labels. Those
  historical results are excluded from the RGB-only benchmark pools here.
- The ANN translation did not match the symbolic controller. No neural
  checkpoint, unfinished selector or automatically resumed experiment is shipped.

The [full audit](AUDIT.md) documents the analytical foundation, experiments,
failed ideas, observation-contract repair, stopped work and remaining gaps.
This release preserves the measured policy rather than silently folding in
unvalidated changes.

## Repository guide

```text
src/crafter_symbolic/
  agent.py              Public RGB-to-action API
  cli.py                Stock environment runner and result export
  viewer.py             Optional display of returned frames
  metrics.py            Achievement rates and Crafter Score
  _policy/              Frozen symbolic controller and RGB decoder
examples/               Minimal integration example
tests/                  Contract, perception, runner and viewer tests
evidence/               Portable benchmark rows and provenance
docs/                   Architecture, benchmarks, audit and maintainer guides
scripts/                Evidence and repository checks
.github/                CI, issue and pull-request templates
```

[Architecture](ARCHITECTURE.md) · [Benchmarks](BENCHMARKS.md) ·
[Audit](AUDIT.md) · [Verification](VERIFICATION.md) ·
[Changelog](../CHANGELOG.md) · [Contributing](../CONTRIBUTING.md)

## Develop and verify

From a virtual environment in the repository root:

```bash
python -m pip install -r requirements.lock -e ".[viewer]"
python -m unittest discover -s tests -v
python scripts/verify_evidence.py
python scripts/verify_repository.py
python -m pip check
```

Omit the viewer extra for headless-only development; the optional display test
will be skipped. Display tests use SDL's offscreen driver and do not open
unsolicited windows.

Local verification uses Python 3.11 on macOS arm64. The repository includes
Linux CI, but a remote CI pass is not claimed before its first GitHub run.
The earlier package transplant also matched all 3,870 actions in six complete
original-versus-packaged episode checks. See
[verification details](VERIFICATION.md) for scope and caveats.

Build an installable wheel with `python -m pip wheel --no-deps . --wheel-dir dist`.
Generated wheels, recordings, results, caches and virtual environments are
ignored by Git. Portable historical evidence is intentionally tracked.
Contribution and release procedures are in [CONTRIBUTING.md](../CONTRIBUTING.md)
and [Publishing](PUBLISHING.md).

## Troubleshooting

| Symptom | What to check |
|---|---|
| `crafter-symbolic: command not found` | Activate the environment where you installed the project; try `python -m crafter_symbolic` |
| “Live viewing needs pygame” | From this root, run `python -m pip install ".[viewer]"` |
| Cannot open a desktop window | Omit `--show`; GIF recording works without a display |
| Output or recording directory already exists | Choose fresh paths; overwriting and automatic resume are intentionally disabled |
| Unsupported observation shape/type | Use the exact stock 64×64×3 uint8 frame, including HUD |
| Very low score from an installation test | `--length 20` is a short smoke, not a benchmark; use the default 10000 |
| “Show requires workers 1” | Watch episodes sequentially; use multiple workers only for headless batches |
| GIF looks small or colors differ slightly | GIFs preserve 64×64 geometry and use a palette; `--scale` only enlarges the live window |
| High memory use while recording | Reduce workers/episodes; frame buffers are retained until each GIF is written |
| Changed code is not being used | Reinstall with `python -m pip install .`, or use an editable development install |

Already using the paper's source checkout? An installed package reporting
Crafter 1.8.3 satisfies the dependency. Keep its stock code/assets/default
rendering; modified copies are outside the verified contract.

## License and acknowledgments

Original agent code and documentation are available under the [MIT license](../LICENSE).
Crafter and the optional viewer are installed dependencies, not vendored code;
their licenses remain separate. See [licensing notes](LICENSING.md).

Crafter was created by Danijar Hafner. Please credit the underlying benchmark
when using it:

> Danijar Hafner. *Benchmarking the Spectrum of Agent Capabilities.* 2021.
> [Paper](https://arxiv.org/abs/2109.06780) · [Crafter repository](https://github.com/danijar/crafter)

When reporting this agent, include the package version or Git commit, observation
contract, episode count, horizon and seed range. No project DOI or hosted package
publication is implied.
