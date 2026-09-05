"""Small diagnostic fixture: damage attribution is not a certified cooldown.

This edits an in-memory test world only. It is not a benchmark episode and
does not modify the released policy. Truth is used for the assertion only.
"""
import json

import crafter
from crafter import objects
import numpy as np

from crafter_symbolic._policy.heuristic_agent import DiamondAgent, SymbolicObservation


def main():
    env = crafter.Env(seed=71)
    env.reset()
    player, world = env._player, env._world
    for obj in tuple(world.objects):
        if obj is not player:
            world.remove(obj)
    origin = np.array(player.pos)
    for dx in range(-2, 3):
        for dy in range(-2, 3):
            world[origin+np.array((dx, dy))] = 'grass'
    left = objects.Zombie(world, origin+(-1, 0), player)
    right = objects.Zombie(world, origin+(1, 0), player)
    world.add(left)
    world.add(right)
    left.health, left.cooldown, right.cooldown = 2, 0, 2
    player.inventory.update(health=9, food=9, drink=9, energy=9, stone_sword=1)
    player.facing, player.action = (-1, 0), 'do'
    before = dict(player.inventory)
    player.update()
    left.update()
    right.update()
    assert player.health == 7 and right.cooldown == 1
    assert left not in world.objects and right in world.objects

    # The same visible before/after evidence reaches the belief updater.
    materials = {(x, y): 'grass' for x in range(-4, 5) for y in range(-3, 4)}
    old = SymbolicObservation(materials, {(-1, 0): 'zombie', (1, 0): 'zombie'},
                              {}, before, (-1, 0), False, 0.0)
    new = SymbolicObservation(materials, {(1, 0): 'zombie'}, {},
                              dict(player.inventory), (-1, 0), False, 0.0)
    agent = DiamondAgent()
    agent.last_observation, agent.last_action = old, 'do'
    agent.enemy_damage = {(-1, 0): ('zombie', 3), (1, 0): ('zombie', 0)}
    agent.zombie_cooldowns = {(-1, 0): 0, (1, 0): 2}
    agent.observe(new)
    inferred = agent.zombie_cooldowns[(1, 0)]
    assert inferred == 5 and inferred != right.cooldown
    print(json.dumps({'kind': 'DIAGNOSTIC_COUNTEREXAMPLE_NOT_BENCHMARK',
                      'health_before': before['health'], 'health_after': player.health,
                      'surviving_zombie_true_cooldown': right.cooldown,
                      'surviving_zombie_inferred_cooldown': inferred,
                      'cause': 'Killed adjacent zombie still attacks on its final update; '
                               'the surviving adjacent zombie is incorrectly credited with the hit.',
                      'classification': 'Overconfident belief inference, not hidden-state access',
                      'policy_modified': False}, indent=2))


if __name__ == '__main__':
    main()
