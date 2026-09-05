# Agent architecture and contract

## One controller, not an episode oracle

`Agent()` contains one fixed `ExpeditionAgent(pocket=True)` instance. The name
reflects its research lineage, not an ensemble. No seed, completed outcome,
privileged world feature, network, or external planner selects its behavior.
The optional `combined` constructor selects a different fixed controller once,
at the caller's request; the default does not switch between benchmark experts.

## Observation boundary

The original Crafter frame has a 9-column, 7-row world area and two HUD rows,
rendered from 7×7 textures inside a 64×64 RGB array. The decoder enumerates
legal public texture combinations, matches HUD and player sprites, and scores
world-cell candidates against the public light/sleep/noise transforms. It reads
the installed game assets, never a live environment. Night scores are geometric
residual/margin scores, **not calibrated posterior probabilities**.

Frozen night margins are 0.12 for material, 1e-9 for object absence, and 0.02
for object presence. They were selected on separate calibration worlds. On the
held-out eight-world night sample, accepted labels had zero observed errors:
6,951 material labels, 7,088 absence labels, 220 presence labels. Coverage was
88.28%, 92.62%, and 99.55% respectively, with different class denominators.
Finite sampled validation does not prove zero perception error on all frames.

Material identity, object presence and certified absence are separate channels.
Missing evidence is unknown, not empty space or `void`. Unknown current evidence
does not erase reliable static memories. Sleeping-facing memory is retained
from earlier visible facing. Relative odometry advances only when a move's
destination was supported by the observation contract. No absolute player
coordinate or full-world dimensions are supplied to the policy state.

Public `Agent.act` deliberately accepts RGB only. The internal visual observation
record is useful for tests, but feeding it true simulator semantics through
ambiguous nighttime pixels would violate the release contract.

## Priority structure

1. Reconcile the last action, visual evidence, inventory and symbolic memory.
2. Apply tactical/safety handling and preserve protected shelter operations.
3. Service water, food, fatigue and night deadlines with resumable tasks.
4. Gather missing prerequisites and craft using remembered resources/utilities.
5. Finish a remembered diamond when the iron pickaxe is available.
6. Otherwise explore reachable frontiers, using mountain geometry as a prior.
7. After diamond, continue survival and pursue missing score achievements.

The core incorporates early stone-sword defense, cheap last-wood deferral,
known-diamond finishing, arrow guards, shelter revalidation, and a radius-five
mountain-information kernel after 300 unresolved post-pick actions. The combined
extension adds a cheaper valid shared forge destination, bounded ripe-food
service, and a narrowly gated local zombie-combat model. It does not enable the
full resource-tour experiment.

The combat pilot evaluates six-step fight, retreat and block continuations on
16 fixed internal random tapes using recognized local enemies and conservative
hidden-state beliefs. These tapes do not access the game's RNG. The pilot is
approximate: it omits spawning/off-screen arrivals and full task/metabolism
continuation. Its sampled survival counts are not safety guarantees. Public
update-order details include the final attack of a zombie killed that step.

## Why pocket is the recommended finish

Pocket adds natural protected crop placement, boundary handling and harvest
service after diamond. It inherits combined, not the stock-rejected Full
composition's mixed/stress combat or broader shelter changes. Provisioning and
excursion experiments are disabled. Review and 128 historical paired pre-diamond
action hashes support exactly the same pre-diamond decision law as combined.

This makes pocket a useful practical choice for additional achievement breadth
without changing the diamond acquisition prefix. It does not prove its whole
episode Score is higher in population. Independently launched stock games can
produce different diamond counts even with identical pre-diamond policy law.

## Memory

All state resets per episode: relative material map; visit counts; recognized
and recently seen objects; oriented arrows; inferred enemy damage/cooldowns;
forge, water, ore, diamond and shelter landmarks; route/goal stages; necessity
clocks; pick/diamond timestamps; recent positions; plant and weapon task state.
There is no cross-episode learning or seed-conditioned memory.

The scheduler's cost/runway estimates are heuristics. For example the inherited
19-value sword admission calculation is a sum-of-distances proxy, not a strict
19-action tour bound. The ripe-food distance-six gate can require another
arrival-facing action. These are disclosed modeling approximations, not hidden
information or benchmark action limits.

## Boundaries of support

Use stock Crafter 1.8.3 default rendering and one action per observation.
Do not teleport the player, alter inventory, override an agent's proposed action,
skip frames, or reuse episode memory across resets. A future DAgger collector
needs a separate executed-action reconciliation contract; this release is the
autonomous player, not that training interface. No claim of optimality,
invulnerability, general-world robustness, or neural imitation parity is made.
