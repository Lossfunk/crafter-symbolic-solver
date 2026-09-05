# Notes on the frozen policy files

These Python modules are kept byte-for-byte as measured, apart from the
package-relative imports recorded in the provenance file. The public wrapper
is `crafter_symbolic.Agent`; don't feed simulator labels into these internal
classes and describe that run as RGB-only.

See the [code map](../../../docs/CODE_MAP.md) for the call path and file roles,
and the [input audit](../../../docs/FINAL_INPUT_AUDIT.md) for assumptions and checks.

Some names and comments come from earlier research:

- “Oracle label” in `score_agent.py` refers to the symbolic label consumed by
  that older layer. In the released call path, it comes from RGB decoding.
- “Absolute” map keys are absolute within the agent's own relative coordinate
  system, whose origin starts at `(0, 0)`. They are not simulator coordinates.
- “Exact” necessity clocks assume a fresh stock reset, correctly decoded
  observations and one executed action per call. They are reconstructed values.
- “Certified” visual evidence means accepted by the decoder's thresholds,
  not mathematically proven correct. Day/HUD/player labels don't all abstain.
- The zombie-cooldown comment claiming an observed hit “pins” a value is too
  strong. The audit includes a counterexample; this is an unfixed belief error.
- The combat `TAPES` are fixed internal samples, unrelated to the game RNG.
- The score-layer flags are estimates of progress. They do not write Crafter's
  achievement counters; reported scores come from the environment runner.

`ExpeditionAgent(pocket=True)` enables only the selected fixed combination.
Other constructor switches and `VARIANTS` entries remain inactive unless an
internal caller explicitly requests them. They are not a per-episode selector.
