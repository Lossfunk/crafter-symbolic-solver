# Benchmarks and uncertainty

## Recommended release

The default is **pocket**, a fixed combined controller with post-diamond crop
handling. Its frozen source achieved **69.98 Crafter score and 213/384 diamonds
(55.47%)** across two completed fresh stock batches. This is our practical
release choice, not a statistically established globally best policy.

| Fixed policy | Completed episodes | Diamonds | Diamond rate, Wilson 95% interval | Pooled Score, bootstrap 95% interval |
|---|---:|---:|---:|---:|
| pocket (default) | 384 | 213 | 55.47% [50.47, 60.36] | 69.98 [67.30, 72.43] |
| combined (optional reference) | 640 | 368 | 57.50% [53.64, 61.27] | 68.73 [66.68, 70.70] |

These are different world cohorts. Do not subtract their pooled means to infer
the effect of pocket. Pocket changes only behavior after diamond; code review
and 128 historical paired pre-diamond action hashes support an unchanged
diamond-acquisition decision law. Separate stock processes can nevertheless
realize different trajectories, including on the same nominal seed.

The 640-episode combined pool includes **all three** unchanged-code fresh
batches: 198000000, 201000000 and 205000000. An earlier 512-episode report used
only the latter two (Score 69.1542; 298 diamonds, 58.2031%). Its arithmetic was
correct but its scope omitted the first batch. The larger pool here corrects
that omission. Policy hashes were checked before pooling.

## Metric and protocol

For achievement i, let p_i be the percentage of episodes obtaining it at least
once. With all 22 achievements:

`Score = exp(mean(log(1 + p_i))) - 1`.

This is a geometric aggregate of **population achievement rates**, not mean
episode reward, average count of achievements, arithmetic mean of batch Scores,
or a score conditioned on collecting diamond. Pooled Scores are recomputed from
pooled episode rows.

Stock Crafter 1.8.3; default world/view/rendering; death or 10,000 environment
actions; no early termination on diamond; exact returned RGB and previous
reward to the agent. Static public textures/mechanics and legal episode-local
memory are allowed. Evaluator-only inventory, achievements and world analysis
are never agent inputs. No additional render call is made.

All 384 pocket and 640 combined episodes in these pools ended in death, before
the limit (maximum lifespans 3,942 and 4,385). Thus the measured shortfall is not
primarily running out of the 10,000-step allowance.

Pooled Score intervals use 10,000 episode/world bootstrap resamples;
diamond intervals use Wilson's binomial interval. They express sampling
uncertainty under the evaluated distribution, not uncertainty about all possible
world generators or all choices made during the wider development process.
Fresh batches were reserved for their named frozen comparisons, not a single
never-opened holdout for the entire research program. Repeated search still
requires caution about selection and multiple comparisons.

## Completed fresh stock comparisons

Batch labels are first seeds; n is **per policy**. Full, bank_pocket and baseline
are audit references, not extra public release modes.

| Batch | n | Policy | Diamonds | Diamond % | Crafter Score |
|---|---:|---|---:|---:|---:|
| 97000000 | 400 | corrected RGB baseline | 207 | 51.75 | 66.7744 |
| 198000000 | 128 | baseline | 64 | 50.00 | 65.3965 |
| 198000000 | 128 | combined | 70 | 54.69 | 66.9775 |
| 201000000 | 256 | baseline | 144 | 56.25 | 68.6411 |
| 201000000 | 256 | combined | 157 | 61.33 | 69.8582 |
| 201000000 | 256 | Full | 138 | 53.91 | 69.1191 |
| 205000000 | 256 | combined | 141 | 55.08 | 68.3975 |
| 205000000 | 256 | pocket | 137 | 53.52 | 69.3763 |
| 206000000 | 128 | pocket | 76 | 59.38 | 71.1236 |
| 206000000 | 128 | bank_pocket | 73 | 57.03 | 70.8027 |

Relevant within-batch contrasts:

- 201 combined versus baseline: diamonds +5.08 percentage points, interval
  [-1.56, 11.72]; Score +1.22, interval [-2.68, 5.12]. Promising, not proven.
- 201 Full versus combined: diamonds **-7.42 points**, interval
  [-13.67, -1.17]; Score -0.74. The development winner did not survive stock
  testing and is not shipped as the recommended agent.
- 205 pocket versus combined: raw Score **+0.98**, interval [-2.24, 4.35].
  Eat-plant rate rose from 6.25% to 9.77%. The supplementary standardized
  Score contrast +1.80 [-0.65, 4.28] is **not** the raw benchmark Score.
- 206 bank_pocket versus pocket: Score -0.32 [-4.62, 3.96]; diamonds
  -2.34 points [-10.16, 5.47]. Five banking activations are not five causal
  rescues. Banking was not promoted.

The records use same-world pairing where appropriate, but stock Python object
iteration/despawn ordering does not supply a fully coupled counterfactual
random tape. An endpoint change in one world is not automatically attributable
to a specific intervention.

## All 22 achievement rates

Percent of whole episodes achieving each item. Human reference is the official
100-game expert dataset; the two agent columns use the pooled cohorts above.

| Achievement | pocket, n=384 | combined, n=640 | Humans, n=100 |
|---|---:|---:|---:|
| collect_coal | 95.31 | 96.41 | 86 |
| collect_diamond | 55.47 | 57.50 | 12 |
| collect_drink | 97.92 | 97.03 | 92 |
| collect_iron | 86.20 | 87.66 | 53 |
| collect_sapling | 47.66 | 52.03 | 67 |
| collect_stone | 99.74 | 99.06 | 100 |
| collect_wood | 100.00 | 99.84 | 100 |
| defeat_skeleton | 73.70 | 73.28 | 31 |
| defeat_zombie | 96.09 | 95.78 | 84 |
| eat_cow | 89.84 | 90.47 | 89 |
| eat_plant | 10.42 | 6.09 | 8 |
| make_iron_pickaxe | 82.55 | 82.81 | 26 |
| make_iron_sword | 31.77 | 30.31 | 22 |
| make_stone_pickaxe | 97.66 | 97.97 | 78 |
| make_stone_sword | 97.66 | 97.97 | 78 |
| make_wood_pickaxe | 100.00 | 99.22 | 100 |
| make_wood_sword | 29.95 | 28.28 | 45 |
| place_furnace | 97.66 | 97.81 | 32 |
| place_plant | 45.31 | 47.34 | 24 |
| place_stone | 90.62 | 90.16 | 90 |
| place_table | 100.00 | 99.22 | 100 |
| wake_up | 85.42 | 87.19 | 73 |

The expert dataset's pooled Score is **52.0497** with 12 diamonds. The paper's
**50.5 ± 6.8** is a different aggregation: five random groups of trajectories,
not five individual players. Do not silently substitute one statistic for the
other. These descriptive profiles are not a controlled human-versus-agent
comparison: external game knowledge, engineering effort and training budgets
are not matched. Source: [official Crafter repository and expert data](https://github.com/danijar/crafter).

## Speed without hiding failures

For pocket's 384 episodes, first-diamond times among the 213 successes range
from 67 to 2,147 actions, median **410**. That conditional median does not
describe unsuccessful episodes. The following cumulative rates keep **all 384
episodes in the denominator**:

| Diamond collected by action | Whole-episode fraction |
|---|---:|
| 100 | 5.47% |
| 200 | 18.49% |
| 400 | 25.78% |
| 800 | 47.14% |
| 1,600 | 53.65% |
| 3,200 | 55.47% |
| 6,400 | 55.47% |
| 10,000 | 55.47% |

We have not established the optimal coverage/speed frontier. No fastest-seed
record, selection-court maximum, or simulator-informed upper bound is presented
as an achievable autonomous-agent rate.

## Portable evidence

[benchmarks.json](../evidence/benchmarks.json) contains **2,192 completed episode
rows** across the five result files above, all 22 achievements, batch and pooled
summaries, source/result hashes, and human reference counts. It includes
comparison policies, so 2,192 is not the default agent's sample size.

[policy_provenance.json](../evidence/policy_provenance.json) records the frozen
controller's source hashes, namespaced hashes and normalized syntax-tree checks.
[packaging_equivalence.json](../evidence/packaging_equivalence.json) records six
complete episode equivalence checks; they are not added to the benchmark pool.

Run `python scripts/verify_evidence.py` after installation to independently
recompute every shipped point estimate and verify transplanted source hashes.
The stopped investment replication, old privileged results, neural trials and
development selection courts are deliberately not pooled into these numbers.
