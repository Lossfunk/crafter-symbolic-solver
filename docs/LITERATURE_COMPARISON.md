# Crafter capability: human and literature context

Checked on **2026-09-05**. This is a source-checked selection of strong results,
not an exhaustive leaderboard or an independent reproduction of other agents.
We make no state-of-the-art or superiority claim for the released agent.
The frozen release's evidence is in [BENCHMARKS.md](BENCHMARKS.md).

## The question we are comparing

Our target is performance on new episodes, each ending at death or at 10,000
environment actions: the probability of collecting diamond at least once and
the official geometric aggregate of all 22 achievement success percentages.
An episode without diamond remains in the denominator, including worlds where
the resource is absent or never observed. Collecting diamond does not end our
evaluation; later achievements count too.

Training length is not an eligibility restriction for this comparison. A
10M-step training run, a 10B-step expert, and a hand-designed solver can all be
informative about attainable capability. They are not equivalent learning
procedures. In particular, “no training required to run this package” does not
mean that designing it used no experiments or external knowledge.

We still distinguish the simulator, map distribution, observations, action
repeat, episode cutoff, and evaluation aggregation. Removing a training-budget
restriction does not remove those differences. “Crafter score” is not return,
normalized return, or the fraction of achievements completed in one episode.

## Pixel agents and the original human reference

| Reference | Score | Diamond success | Training / preparation context | Source |
|---|---:|---:|---|---|
| This release, `pocket` | 69.98 | 55.47% (213/384) | Hand-designed priors and iterative experiments | [Frozen evidence](BENCHMARKS.md) |
| Human experts | 50.5 ± 6.8 | 12% (12/100) | Human experience and practice | [Hafner, Tables 1 and C.1](https://arxiv.org/abs/2109.06780v2) |
| DreamerV3 (XL) | 39.6 | 0.0% | 10M environment steps | [EMERALD paper, Table 5](https://proceedings.mlr.press/v267/burchi25a/burchi25a.pdf) |
| Delta-IRIS | 42.5 | 0.0% | 10M environment steps | [EMERALD paper, Table 5](https://proceedings.mlr.press/v267/burchi25a/burchi25a.pdf) |
| EMERALD | 58.1 | 0.5% | 10M environment steps | [Burchi and Timofte, Tables 2 and 5](https://proceedings.mlr.press/v267/burchi25a/burchi25a.pdf) |
| C-VPT (large) | 61.4 ± 4.7 | Approximately 13%, read from plot | Imitation of CrafterPlay demonstrations; expert trained for 10B steps | [Park et al., Table 1 and Figure 11](https://arxiv.org/html/2508.13530v1) |

The DreamerV3/Delta-IRIS rows are explicitly values reproduced in EMERALD's
comparison, not fresh measurements by this project. Zero means reported zero,
not proof that a method can never collect diamond. C-VPT's diamond value is a
visual estimate from its large-model bar, not an exact count extracted from
evaluation logs. Its 71.3% Table 1 entry is **normalized return**, not diamond
success. The expert's 71% diamond result belongs to a different policy.

### Human aggregation

The original paper specifies the 10,000-step termination limit in Section 3.1.
Table C.1 contains rates across 100 human games; its caption explains that Score
is computed after splitting those games into five random groups. Hence the
paper's **50.5 ± 6.8** is not the Score of the pooled 22-rate vector. Applying
the release's pooled estimator to those rates gives **52.0497**. Both numbers
are useful, but they must be labeled. The groups are not five individual
players. Our human comparison is descriptive, not a controlled population
comparison with matched priors or observation resolution.

### EMERALD horizon and observation check

The paper's Figure 6 describes 256 evaluation episodes; Table 5 explicitly
provides both Score and all 22 rates. Public source at commit
`665948d8cd619ccc960abe54ffdfc785ce95f18b` supports the 10k evaluation setting:

- [Crafter adapter](https://github.com/burchim/EMERALD/blob/665948d8cd619ccc960abe54ffdfc785ce95f18b/nnet/envs/crafter/crafter_env.py)
  uses 64×64 pixels and action repeat 1. It disables the simulator's internal
  length termination with `length=False`.
- [Model configuration and evaluation](https://github.com/burchim/EMERALD/blob/665948d8cd619ccc960abe54ffdfc785ce95f18b/nnet/models/emerald.py)
  sets `time_limit_eval=10000`, installs a time-limit wrapper, and also breaks
  the evaluation loop at that limit. The disabled inner cutoff therefore does
  **not** imply unlimited evaluation episodes.

This checks the released default, not the unpublished provenance of every
paper run. The 58.1 result is the published paper value, not a newly recomputed
score from the repository's later logs.

### C-VPT protocol and uncertainty

The paper describes Crafter evaluation over 100 episodes, aggregated into five
20-episode chunks, using 144×144 pixels. It states the standard Crafter
protocol; the 10k interpretation follows that statement, rather than an
independent reproduction. The released
[evaluation adapter](https://github.com/frechele/CrafterDojo/blob/8a922a3da37bac9d278d4ceac8f78fc457cf01f3/crafterdojo/env/crafter/__init__.py)
constructs a vendored Crafter environment at that resolution. We have not
established byte-equivalence to stock `crafter==1.8.3` or reproduced its cutoff.

C-VPT is a strong pixel-agent reference, not a strictly matched 64×64 baseline.
Its stated error bars also differ from our pooled-bootstrap confidence interval.

## Higher numbers in related settings

| Reference | Score | Diamond success | Why it is separate |
|---|---:|---:|---|
| CrafterDojo expert / CrafterPlay | 97.5 | 71% | Craftax-Classic symbolic-input expert demonstration generator |
| SCALAR | Not reported alongside this result | 88.2% | Craftax-Classic, symbolic input, guaranteed diamond presence |

CrafterDojo's Table 1 and results paragraph give **97.5 / 71%**. Appendix B
specifies Craftax-Classic-Symbolic training and a 10,000-step demonstration
limit. The released
[trajectory generator](https://github.com/frechele/CrafterDojo/blob/8a922a3da37bac9d278d4ceac8f78fc457cf01f3/toolkit/expert/generate_trajectory.py)
actually creates `Craftax-Classic-Symbolic-v1` with `max_steps=10000`.
We therefore treat this expert-demonstration result as related-setting evidence,
not a verified stock-Crafter RGB result. It must not be attributed to C-VPT.
[Paper](https://arxiv.org/html/2508.13530v1).

SCALAR's Table 1 reports **88.2% diamond** on **Craftax-Classic**, at 1B
training frames averaged over five seeds. Section 5.1 explicitly specifies the
10,000-step limit and at least one diamond per map. Inputs include symbolic
inventory, a local 7×9 map and relative entity positions. The same table also
contains results for the larger, multi-floor **Craftax**, whose Appendix A
limit is 100,000 steps; those must not be mixed into a 10k Crafter comparison.
The table reports selected achievement rates, not the official all-22 aggregate.
[SCALAR, Table 1, Section 5.1 and Appendix A](https://arxiv.org/html/2603.09036v1).

## Interpretation, not a ranking

Our result demonstrates substantial attainable capability for this particular
CPU-only symbolic solver. It does not establish state-of-the-art performance,
an optimal policy, or superiority over humans or other agents. These are
separately reported measurements, not a controlled common-protocol evaluation.

“Symbolic input” describes how observations are supplied, not whether a policy
is hand-coded or neural. Our agent constructs symbolic memory from RGB; the
related-setting experts receive structured game facts. Craftax-Classic is a
reimplementation, and matching the 10,000-step limit alone does not make its
worlds or observations identical to stock Crafter.

The higher related-setting results remain important evidence of capability.
Separating them is not a reason to dismiss them or to assume their advantage
is explained by easier inputs or worlds. We have not isolated the contributions
of policy quality, observation access and environment differences to the gap.

The literature check covered the stored Crafter, DreamerV3, Curious Replay,
Achievement Distillation, Delta-IRIS, EMERALD, CrafterDojo, SCALAR, SGRL,
EnvGen, SPRING, planning and human-exploration papers, plus targeted online
searches for newer methods and primary-source code checks. The README selects
only a few informative references, rather than reproducing a long leaderboard.

Important exclusions and interpretation traps:

- The [official Crafter scoreboard](https://github.com/danijar/crafter)
  restricts its RL and unsupervised categories to 1M training interactions. Its
  19.4 Curious Replay entry is not an unlimited-training SOTA ceiling.
- [DiscoRL](https://www.nature.com/articles/s41586-025-09761-x), Extended Data
  Table 5, reports **return 14.56** for Disco103 at 20M training steps. This is
  not an official geometric Crafter Score or a diamond percentage.
- CrafterDojo's instruction-following and hierarchical-task results include
  pre-equipped starts, task-specific rewards, 1,000-step limits and a simplified
  plant task. They are not whole-game Score/diamond results.
- A report of unlocking all 22 achievements at least once across a batch does
  not mean every episode unlocked all 22. Nor does the largest training step
  on a learning curve specify the per-episode horizon.
- We do not infer exact diamond rates from aggregate Score or normalized
  return. The C-VPT plot estimate is explicitly marked approximate; unavailable
  metrics remain unavailable.

No new policy trials or external-agent reproductions were run for this
documentation update. A genuine common-protocol comparison would freeze every
agent, reconcile its observation contract, and evaluate independent episodes
with one agreed 10k-action harness and consistent aggregation.
