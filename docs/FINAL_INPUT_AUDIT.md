# Final input and assumption audit

Checked on 2026-09-05 against release 2.0.7. The subsequent documentation
release leaves the measured policy Python files and public action wrapper
unchanged. This report supplements the [research audit](AUDIT.md).

## Finding

No new hidden-state input was found in the shipped agent. `Agent()` is one
fixed controller with episode-local memory, not a selection of whichever agent
won each game. The reported default remains 213/384 diamonds and Score 69.98.

There is one newly demonstrated bad inference: the agent can attribute damage
to the wrong zombie and become overconfident about its cooldown. That is a
belief error, not access to the true cooldown. It is documented below and has
not been fixed or silently folded into the measured agent.

This is a source review and targeted executable audit, not a formal proof that
no possible defect exists.

## What was checked

- Reviewed the public boundary, decoder, memory updates, active configuration,
  method dispatch, local combat model, runner and scoring path. Checked policy
  imports and calls for simulator, file, network, environment-variable and
  dynamic-code channels.
- Replayed six complete recorded RGB streams, totaling 6,634 actions, without
  importing Crafter or creating an environment in the replay processes. Every
  action matched the original recording, including both successful games.
- Reset the same agent objects after their whole episodes and matched all
  6,634 actions again. The action loop made no file reads. Python audit hooks
  would have rejected file access outside static sprite reads, network access,
  subprocesses and live-environment imports. This is a diagnostic guard, not a
  security sandbox for hostile Python code.
- Used zero rewards on the first replay and varied rewards after reset. Both
  matched: the current rules don't use reward. Input arrays were not modified.
- Compared fixed `combined` with fixed `pocket` on the same observation streams:
  all 4,444 pre-diamond actions matched. These were two audit subjects; the
  deployed default still contains only one controller.
- Checked all 2,192 portable benchmark rows against their original result
  files, verified those file hashes, and recomputed the published summaries.
  The default's 256- and 128-game batches have complete consecutive seed ranges,
  with no filtering for diamond presence or success. Their archived policy
  source hashes match the frozen source used for packaging.
- Reviewed the archived evaluator. Its global-map, true-position and damage
  reads are diagnostics, never arguments to `agent.act`. Reported achievements
  come from Crafter's `info`, not the agent's estimated progress flags.

[Machine-readable results](../evidence/input_boundary_audit.json) preserve
the checked source hashes, recording hashes and per-record replay counts.

## Why it is one agent

`Agent()` constructs one `ExpeditionAgent(pocket=True)`. Its inherited methods
share the same memory. Tactical, food, crafting and exploration modes are
branches of that program, not independent attempts with the best one retained.
The local combat calculation tries hypothetical continuations of its own
belief state; it neither clones nor steps the real environment.

Default settings enable pocket crops, food distance 6, forge return and combat.
Provisioning, excursions and the full resource-tour experiment are off. The
public `combined` option is selected once by the caller; it is not an automatic
expert selector. See the [code map](CODE_MAP.md).

## Assumptions that must be disclosed

| Assumption | Assessment |
|---|---|
| Exact public sprites, HUD layout and rendering transforms | Strong game-specific prior. The decoder loads the installed PNGs and models lighting, tint and noise. This is much more engineered perception than an ordinary learned visual policy, but it reads no live hidden labels. |
| Known clock and reset | The agent counts its own actions and assumes the stock 300-action day cycle, initial phase and initial metabolic counters. It doesn't read the simulator clock. Random-phase starts, dropped frames or action overrides would break this assumption. |
| Public recipes, combat and generation rules | Tool requirements, damage, hunger, sleep and mountain-biased diamond search are supplied knowledge. Development also used simulator truth for perception calibration and diagnostics. This is not learning from pixels without privileged development tools. |
| Accepted visual labels treated as facts | Night world labels use empirical margins. Day labels, HUD digits and player-facing/sleep state use best matches without equivalent abstention. “Certified” is too strong if read as a proof of correctness. Changed rendering or ambiguous frames can produce wrong labels. |
| Persistent map and reconstructed state | The map contains remembered observations, not a supplied world map. Odometry and enemy identity can drift or become mistaken. Static template caches survive reset; episode maps, goals and clocks do not. |
| Enemy health and cooldown estimates | Inferred from prior images, actions and health changes, not read from creatures. Attribution can be wrong; see the counterexample below. |
| Planning costs and safety estimates | Route costs, food runway and the six-step combat model are approximations. They do not guarantee safe routes, survival or globally optimal actions. |
| Unrestricted computation between actions | The cap is 10,000 game actions, not human reaction time, a decision-time budget or limited symbolic memory. This roughly 5,700-line policy is not a tiny decision tree. |

These assumptions fit the stated task of a memory-bearing symbolic agent with
hand-coded priors. They would not fit a stricter claim of human-equivalent
perception, a general-purpose visual agent, or a matched-budget learned policy.

Night perception is still worth particular care: the decoder can recover
information from dim pixels using the known renderer more precisely than a
casual human glance. That differs from the old violation, where true simulator
labels were supplied regardless of what the image contained. The shipped
call path does not contain that old adapter.

## Concrete counterexample: wrong zombie cooldown

In an isolated fixture using stock object-update code, two zombies are next to
the player. The player kills the left one, which still attacks on its final
update. The right zombie does not attack; its real cooldown falls from 2 to 1.
The player loses two health and only the right zombie remains visible.

The belief updater attributes the hit to that survivor and sets its estimated
cooldown to 5. True value: 1. Estimated value: 5. This can create a falsely safe
window. The older comment that a hit “pins” the cooldown is therefore too
strong. No true cooldown enters the policy; only the audit reads it to check
the claim. This example establishes a possible error, not its frequency or
effect on the benchmark score.

Run [the counterexample](../scripts/audit_assumptions.py) with:

```bash
python scripts/audit_assumptions.py
```

It changes only an in-memory test fixture, not a saved game or policy file.
Fixing the inference would produce a new candidate needing separate tests and
score measurements. This audit does not make that change.

## Benchmark caveats

The current agent and score are separate from the historical privileged-night
baseline. Those old results are not included in the 384-game default pool.
The pool uses the same fixed policy across complete batches; it is not a
best-of-several-policy score.

The historical harness wrapped stock object updates to log damage and read
world state for diagnostics. Review found no policy input or deliberate change
to game rules/RNG calls through those probes. Still, instrumentation and Python
object ordering can change same-seed trajectories; we have not replayed every
historical episode in a fresh uninstrumented runner. The six gallery recordings
use the clean public runner pattern, but are selected illustrations, not a
replacement benchmark.

Repeated development and selection also mean the published sample is not one
never-inspected holdout for the entire project. The result is a measured fixed
policy, not an upper bound or a SOTA claim. All 384 default benchmark episodes
ended in death before 10,000 actions.

## Recheck the input boundary

After recording games with [record_gallery.py](../scripts/record_gallery.py):

```bash
python scripts/audit_boundary.py --record-dir runs/gallery --workers 3 --output runs/boundary-audit.json
python scripts/verify_evidence.py
```

Use a fresh output path. The replay uses saved RGB arrays, not GIFs: GIF palette
conversion and frame sampling make them unsuitable as exact action witnesses.

[Back to README](../README.md)
