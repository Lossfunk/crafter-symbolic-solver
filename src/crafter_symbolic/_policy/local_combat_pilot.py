"""Small stochastic local combat pilot, using observed symbolic beliefs only.

Not an environment clone: excludes spawns, metabolism, projectiles and unknown
terrain. The admission gate makes these limitations explicit. Uniform tapes
are internal fixed quadrature samples, unrelated to the environment RNG.
"""
from __future__ import annotations
from collections import Counter
import random

from .heuristic_agent import ACTION_DIRECTIONS, DIRECTIONS, WALKABLE, add, sub, manhattan


def toward(source, target, long_axis):
  dx, dy = sub(target, source)
  choose_x = abs(dx) > abs(dy) if long_axis else abs(dx) <= abs(dy)
  return ((dx > 0) - (dx < 0), 0) if choose_x else (0, (dy > 0) - (dy < 0))


def transition(state, action, terrain, blockers, damage, uniforms, order):
  """One player action then ordered zombie updates; returns immutable state."""
  p, face, health, stone, walls, enemies = state
  enemies = [list(enemy) for enemy in enemies]
  walls = set(walls)
  occupied = {e[0] for e in enemies if e[1] > 0} | set(blockers)
  if action in ACTION_DIRECTIONS:
    face = ACTION_DIRECTIONS[action]
    q = add(p, face)
    if terrain.get(q) in WALKABLE and q not in walls and q not in occupied:
      p = q
  elif action == "do":
    q = add(p, face)
    for enemy in enemies:
      if enemy[0] == q and enemy[1] > 0:
        enemy[1] -= damage
        break
  elif action == "place_stone" and stone:
    q = add(p, face)
    if terrain.get(q) in WALKABLE and q not in walls and q not in occupied:
      walls.add(q)
      stone -= 1
  removed = set()
  for index in order:
    position, enemy_health, cooldown = enemies[index]
    # A killed zombie is removed before its move (World.move then refuses),
    # but still attacks from its old position on this final update.
    if enemy_health <= 0:
      removed.add(index)
    if enemy_health > 0:
      occupied = {e[0] for j, e in enumerate(enemies)
                  if j != index and j not in removed} | set(blockers) | {p}
      u, v = uniforms[index]
      if manhattan(position, p) <= 8 and u < 0.9:
        direction = toward(position, p, v < 0.8)
      else:
        direction = tuple(DIRECTIONS)[min(3, int(v * 4))]
      q = add(position, direction)
      if terrain.get(q) in WALKABLE and q not in occupied and q not in walls:
        position = q
    if manhattan(position, p) <= 1:
      if cooldown:
        cooldown -= 1
      else:
        health = max(0, health - 2)
        cooldown = 5
    enemies[index] = [position, enemy_health, cooldown]
  return (p, face, health, stone, frozenset(walls),
          tuple(tuple(e) for e in enemies if e[1] > 0))


def continuation(state, mode, terrain, blockers):
  p, face, health, stone, walls, enemies = state
  if not enemies:
    return "noop"
  adjacent = [e for e in enemies if manhattan(e[0], p) == 1]
  occupied = {e[0] for e in enemies} | set(blockers)
  def free(q):
    return terrain.get(q) in WALKABLE and q not in occupied and q not in walls
  if mode in DIRECTIONS.values():
    q = add(p, ACTION_DIRECTIONS[mode])
    if free(q):
      return mode
  if mode == "block" and stone:
    q = add(p, face)
    if free(q) and any(manhattan(q, e[0]) == 1 for e in enemies):
      return "place_stone"
  if adjacent:
    target = min(adjacent, key=lambda e: (e[0] != add(p, face), e[1], e[0]))[0]
    direction = sub(target, p)
    return "do" if direction == face else DIRECTIONS[direction]
  # Non-fight continuations wait behind their cover if their ray is blocked.
  if mode != "fight":
    return "noop"
  target = min(enemies, key=lambda e: (manhattan(e[0], p), e[0]))[0]
  choices = [(manhattan(add(p, d), target), action)
             for d, action in DIRECTIONS.items() if free(add(p, d))]
  return min(choices)[1] if choices else "noop"


_random = random.Random(1709)
TAPES = tuple(tuple(tuple((_random.random(), _random.random()) for _ in range(2))
                    for _ in range(6)) for _ in range(16))


def combat_action(agent, obs, baseline):
  inv = obs.inventory
  if not 2 <= inv.get("health", 0) <= 6 or not inv.get("stone_sword", 0):
    return None
  if any(inv.get(n, 0) < 2 for n in ("food", "drink", "energy")):
    return None
  if any(n in {"arrow", "skeleton"} for n in agent.visible_objects.values()):
    return None
  zombies = sorted(p for p, n in agent.visible_objects.items() if n == "zombie")
  if not 1 <= len(zombies) <= 2 or min(manhattan(p, agent.position) for p in zombies) > 2:
    return None
  # No optimistic use of unseen tiles, or partially decoded local cells.
  terrain = {p: agent.materials[p] for p in agent.current_visible_cells
             if p in agent.materials}
  blockers = {p for p, n in agent.visible_objects.items() if n != "zombie"}
  if any(manhattan(p, agent.position) <= 2 for p in blockers):
    return None
  agent.opportunities["combat_eligible_frames"] += 1
  damage = 5 if inv.get("iron_sword", 0) else 3
  enemies = tuple((p, max(1, 5 - agent.enemy_damage.get(p, ("zombie", 0))[1]),
                   agent.zombie_cooldowns.get(p)) for p in zombies)
  roots = ["noop", "do", *DIRECTIONS.values()]
  if inv.get("stone", 0):
    roots.append("place_stone")
  if baseline not in roots:
    return None
  modes = ["fight", "block", *DIRECTIONS.values()]
  values = {}
  for first in roots:
    outcomes = []
    for mode in modes:
      alive, quality = 0, 0.0
      for sample, tape in enumerate(TAPES):
        # Ambiguous cooldowns are evaluated over their whole legal range,
        # not silently treated as a favorable observed safe window.
        scenario = tuple((p, hp, cooldown if cooldown is not None else sample % 6)
                         for p, hp, cooldown in enemies)
        state = (agent.position, agent.facing, inv["health"], inv.get("stone", 0),
                 frozenset(), scenario)
        for tick in range(6):
          action = first if tick == 0 else continuation(state, mode, terrain, blockers)
          order = tuple(range(len(state[-1])))
          if sample % 2:
            order = tuple(reversed(order))
          state = transition(state, action, terrain, blockers, damage, tape[tick], order)
          if state[2] <= 0:
            break
        if state[2] > 0:
          alive += 1
          killed = len(enemies) - len(state[-1])
          separation = min((manhattan(state[0], e[0]) for e in state[-1]), default=4)
          quality += (5 * state[2] + 6 * killed + min(4, separation)
                      - 2 * (inv.get("stone", 0) - state[3]))
      outcomes.append((alive, quality / len(TAPES), mode))
    values[first] = max(outcomes)
  best = max(roots, key=lambda a: (values[a][:2], a == baseline))
  before, after = values[baseline], values[best]
  # A small, fixed admission margin; this is a pilot, not tuned per court.
  if best != baseline and (after[0] >= before[0] + 2 or
                           (after[0] == before[0] == 16 and after[1] >= before[1] + 8)):
    agent.opportunities["combat_model_overrides"] += 1
    agent.opportunities["combat_action_" + best] += 1
    agent.combat_event = {
        "step": agent.step + 1, "baseline": baseline, "proposed": best,
        "baseline_model_value": before, "selected_model_value": after,
        "enemy_beliefs": enemies,
    }
    return best
  return None
