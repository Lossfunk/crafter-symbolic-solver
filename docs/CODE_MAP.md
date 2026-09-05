# Reading the code

Start with [the small working example](../examples/play.py), then
[the public API](../src/crafter_symbolic/agent.py). You don't need the research
folder, saved games or a model service to run the agent.

## One action, end to end

```text
Crafter reset/step → returned RGB + previous reward
  Agent.act
    CrafterRGBDecoder.decode → local labels, unknown cells, HUD
    CorrectedAgent.act_visual → uncertainty-aware observation
    DiamondAgent.act
      update memory → tactical / survival / task methods → final guards
  integer action → one Crafter step
```

The environment runner and the policy are separate. The runner can inspect
`info` to score or record a game. `Agent.act` is never given `info`, an
environment object, a seed or an absolute position. Reward is accepted for
API compatibility but is not currently used by the decision rules.

## Where each part lives

| Part | File | Start with |
|---|---|---|
| Public input/output and episode reset | [agent.py](../src/crafter_symbolic/agent.py) | `Agent.act`, `Agent.reset` |
| Active fixed settings | [config.py](../src/crafter_symbolic/_policy/config.py) | `FINAL_CONFIG` |
| RGB, HUD and night decoding | [crafter_rgb_decoder.py](../src/crafter_symbolic/_policy/crafter_rgb_decoder.py) | `decode`, `rank_cell`, `_candidate_scores` |
| Present / absent / unknown distinction | [visual_symbolic_observation.py](../src/crafter_symbolic/_policy/visual_symbolic_observation.py) | `VisualSymbolicObservation` |
| Handling ambiguous observations | [corrected_symbolic_agent.py](../src/crafter_symbolic/_policy/corrected_symbolic_agent.py) | `act_visual`, `observe`, `_commit_previous_action` |
| Memory, routes, resources, shelter and main priorities | [heuristic_agent.py](../src/crafter_symbolic/_policy/heuristic_agent.py) | `observe`, `dijkstra`, `survival_action`, `task_action`, `act` |
| Mountain-search prior and post-diamond achievements | [score_agent.py](../src/crafter_symbolic/_policy/score_agent.py) | `mountain_kernel_value`, `score_task_action` |
| Food, forge return and combat extension | [symbolic_opportunity_agent.py](../src/crafter_symbolic/_policy/symbolic_opportunity_agent.py) | `OpportunityAgent.__init__`, `tactical_action`, `task_action` |
| Local hypothetical combat | [local_combat_pilot.py](../src/crafter_symbolic/_policy/local_combat_pilot.py) | `combat_action`, `transition` |
| Default pocket addition | [symbolic_expedition_agent.py](../src/crafter_symbolic/_policy/symbolic_expedition_agent.py) | `ExpeditionAgent.__init__`, `choose_protected_plant_enclosure`, `farm_harvest_action` |
| Whole episodes, parallel batches and full GIFs | [cli.py](../src/crafter_symbolic/cli.py) | `run_episode`, `main` |
| Optional live window | [viewer.py](../src/crafter_symbolic/viewer.py) | `FrameViewer` |
| The 22-achievement score | [metrics.py](../src/crafter_symbolic/metrics.py) | `summarize` |

## Why several classes still mean one agent

The default object's inheritance chain is:

```text
ExpeditionAgent → OpportunityAgent → CorrectedAgent → CrafterScoreAgent → DiamondAgent
```

These are layers of methods on one object, sharing one episode memory. They
are not separately played agents whose best results are chosen afterward.
The default enables `pocket`, food distance 6, forge return and combat.
Provisioning, excursions and the full resource tour are disabled. Internal
`VARIANTS` dictionaries preserve earlier experiments; the public API exposes
only fixed `pocket` and fixed `combined`, chosen once by the caller.

## What is deliberately kept intact

The policy folder contains about 5,700 lines, including inactive experimental
branches. This is a substantial hand-engineered program, not a tiny decision
tree. The largest file retains its section headings and method names so it
still matches the measured source. We have not split or reformatted it just
for appearance: doing so would weaken the direct source-hash comparison.

[Notes beside the policy files](../src/crafter_symbolic/_policy/README.md)
explain the old names and comments. Some comments say “oracle,” “exact” or
“certified” more strongly than the current implementation warrants. The
[final input audit](FINAL_INPUT_AUDIT.md) identifies the important cases.

## Tests, recordings and evidence

- [Usage](USAGE.md) covers commands, installation and embedding.
- [Gameplay](GAMEPLAY.md) maps the inline GIFs to recordings and the
  [recording](../scripts/record_gallery.py) and [rendering](../scripts/render_gallery.py) scripts.
- [Tests](../tests/) check the API, perception boundary, metrics and GIFs.
- [Source and documentation checks](../scripts/verify_repository.py) check versions,
  licenses, CLI coverage and local links.
- [Evidence checks](../scripts/verify_evidence.py) recompute the shipped benchmark
  rows and verify the measured policy hashes.
- [Offline boundary audit](../scripts/audit_boundary.py) replays saved RGB with
  no live environment import, repeats after reset, and checks the combined prefix.
- [Assumption counterexample](../scripts/audit_assumptions.py) demonstrates the
  known zombie-cooldown attribution error in an isolated test fixture.
- [Verification record](VERIFICATION.md) states what was actually checked.
  [Publishing](PUBLISHING.md) covers building and pushing the repository.

[Back to README](../README.md)
