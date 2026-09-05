"""Isolated RGB-only experiments; the corrected champion stays unchanged."""
from __future__ import annotations

from collections import Counter
import heapq
import itertools

from .corrected_symbolic_agent import CorrectedAgent
from .heuristic_agent import DIRECTIONS, WALKABLE, add, sub, chebyshev


class OpportunityAgent(CorrectedAgent):
  def __init__(self, *, food_distance=0, tour=False, forge_return=False,
               combat=False, decoder=None):
    super().__init__(decoder=decoder)
    self.food_distance = food_distance
    self.tour_enabled = tour
    self.forge_return_enabled = forge_return or tour
    self.combat_enabled = combat
    self.combat_event = None
    self.opportunities = Counter()
    self._food_pending = None
    self._tour_target = None
    self._tour_inventory = None
    self._tour_retry = -1

  def reset(self):
    self.__init__(food_distance=self.food_distance, tour=self.tour_enabled,
                  forge_return=self.forge_return_enabled, combat=self.combat_enabled,
                  decoder=self.decoder)

  def act_visual(self, visual):
    self.combat_event = None
    action = super().act_visual(visual)
    if self.combat_event is not None:
      self.combat_event["executed"] = action
      matched = action == self.combat_event["proposed"]
      self.opportunities["combat_executed" if matched else "combat_vetoed"] += 1
    return action

  def tactical_action(self, obs):
    baseline = super().tactical_action(obs)
    if self.combat_enabled:
      from .local_combat_pilot import combat_action
      proposed = combat_action(self, obs, baseline or "noop")
      if proposed is not None:
        return proposed
    return baseline

  def observe(self, obs):
    pending = self._food_pending
    super().observe(obs)
    # Credit only an executed harvest followed by visible food gain. No
    # proposal-time achievement mutation: the inherited final shield can veto.
    if pending and self.last_action == "do":
      target, previous_food = pending
      if obs.inventory.get("food", 0) > previous_food:
        self.score_eat_plant_done = True
        self.opportunities["food_confirmed_harvests"] += 1
    self._food_pending = None

  def ripe_food_action(self, obs):
    if not self.food_distance or not obs.inventory.get("diamond", 0):
      return None
    ripe = [p for p, name in self.visible_objects.items()
            if name == "plant_ripe"]
    if not ripe:
      return None
    self.opportunities["food_ripe_eligible_frames"] += 1
    # Do not mine or build bridges to reach a snack. Only certified empty,
    # remembered walkable cells, with current hazards handled by main act().
    distance, parent = {self.position: 0}, {}
    queue = [(0, self.position)]
    while queue:
      cost, p = heapq.heappop(queue)
      if distance[p] != cost or cost >= self.food_distance:
        continue
      for direction in DIRECTIONS:
        q = add(p, direction)
        if self.materials.get(q) not in WALKABLE or q in self.visible_objects:
          continue
        if cost + 1 < distance.get(q, 10**9):
          distance[q], parent[q] = cost + 1, p
          heapq.heappush(queue, (cost + 1, q))
    choices = []
    for target in ripe:
      for facing in DIRECTIONS:
        stand = sub(target, facing)
        if stand not in distance:
          continue
        cost = distance[stand] + 1 + int(
            stand == self.position and self.facing != facing)
        if cost <= self.food_distance:
          choices.append((cost, target, stand, facing))
    if not choices:
      return None
    _, target, stand, facing = min(choices)
    if stand != self.position:
      action = self.follow(self.reconstruct(parent, self.position, stand), obs)
    else:
      action = "do" if self.facing == facing else DIRECTIONS[facing]
      if action == "do":
        self._food_pending = (target, obs.inventory.get("food", 0))
    self.opportunities["food_service_proposals"] += 1
    return "ripe_food_service", action

  def survival_action(self, obs):
    decision = super().survival_action(obs)
    # Only replace food servicing, never water, shelter, rest or tactical work.
    if decision and decision[0] in {"hunt_cow", "reacquire_cow", "search_food",
                                    "buffer_search_food"}:
      return self.ripe_food_action(obs) or decision
    return decision

  def _leg(self, start, facing, terrain, goal, inventory, *, harvest=False):
    """Shortest orientation-aware known-terrain leg, with mining macros.

    Mine actions change terrain for later legs. Water/lava are excluded so
    this optional optimization cannot spend an unbudgeted bridge reserve.
    The terminal resource is harvested from a neighbor, not entered.
    """
    initial = (start, facing)
    distance, parents = {initial: 0}, {}
    queue = [(0, initial)]
    terminal = None
    tool = self.tool_level(inventory)
    while queue:
      cost, state = heapq.heappop(queue)
      if cost != distance[state]:
        continue
      p, face = state
      if not harvest and p == goal:
        terminal = state
        break
      if harvest and add(p, face) == goal:
        terminal = state
        break
      for direction in DIRECTIONS:
        q = add(p, direction)
        if q in self.visible_objects:
          continue
        material = terrain.get(q)
        if material in WALKABLE:
          nxt, edge, actions = (q, direction), 1, (DIRECTIONS[direction],)
        elif material and self.mineable(material, tool):
          turn = () if face == direction else (DIRECTIONS[direction],)
          if harvest and q == goal:
            # A blocked turn changes facing without changing position.
            nxt, edge, actions = (p, direction), len(turn), turn
          else:
            nxt, edge = (q, direction), len(turn) + 2
            actions = turn + ("do", DIRECTIONS[direction])
        else:
          continue
        if nxt == state:
          continue
        candidate = cost + edge
        if candidate < distance.get(nxt, 10**9):
          distance[nxt] = candidate
          parents[nxt] = (state, q, material, actions)
          heapq.heappush(queue, (candidate, nxt))
    if terminal is None:
      return None
    segments, state = [], terminal
    while state != initial:
      previous, q, material, actions = parents[state]
      segments.append((q, material, actions))
      state = previous
    edited, carried, actions = dict(terrain), dict(inventory), []
    for q, material, macro in reversed(segments):
      actions.extend(macro)
      if "do" in macro:
        edited[q] = "grass" if material == "tree" else "path"
        item = "wood" if material == "tree" else material
        carried[item] = min(9, carried.get(item, 0) + 1)
    if harvest:
      material = edited.get(goal)
      if material not in {"coal", "iron"}:
        return None
      actions.append("do")
      edited[goal] = "path"
      carried[material] = min(9, carried.get(material, 0) + 1)
    return len(actions), terminal[0], terminal[1], edited, carried, actions

  def _plan_tour(self, obs):
    distance, _, common = self.common_forge_cells(obs)
    common = [p for p in common if self.materials.get(p) in WALKABLE]
    if not common:
      return None
    missing = [m for m in ("coal", "iron") if obs.inventory.get(m, 0) < 1]
    if not missing:
      return None
    candidates = {}
    for material in missing:
      choices = sorted((distance[p], p) for p, value in self.materials.items()
                       if value == material and p in distance)
      if not choices:
        return None
      candidates[material] = [p for _, p in choices[:3]]
    self.opportunities["tour_planning_calls"] += 1
    options = []
    for order in itertools.permutations(missing):
      for targets in itertools.product(*(candidates[m] for m in order)):
        p, face, terrain, inventory = (self.position, self.facing,
                                      self.materials, obs.inventory)
        total, first_action = 0, None
        valid = True
        for material, target in zip(order, targets):
          if inventory.get(material, 0) >= 1:
            continue  # Incidental mining already supplied this ingredient.
          leg = self._leg(p, face, terrain, target, inventory, harvest=True)
          if leg is None:
            valid = False
            break
          cost, p, face, terrain, inventory, actions = leg
          total += cost
          first_action = first_action or actions[0]
        if not valid:
          continue
        endings = []
        for cell in common:
          leg = self._leg(p, face, terrain, cell, inventory)
          if leg is not None:
            endings.append((leg[0], cell))
        if endings:
          return_cost, forge = min(endings)
          options.append((total + return_cost, order, targets, forge, first_action))
    if not options:
      return None
    best = min(options)
    # Compare with the incumbent's nearest-resource, coal-first tour on the
    # same cost model. A margin avoids changing trajectories for tiny ties.
    baseline_targets = tuple(candidates[m][0] for m in missing)
    baseline = [x for x in options if x[1] == tuple(missing)
                and x[2] == baseline_targets]
    if not baseline or min(baseline)[0] - best[0] < 3:
      return None
    self.opportunities["tour_selected"] += 1
    self.opportunities["tour_predicted_savings"] += min(baseline)[0] - best[0]
    if best[1][0] != missing[0]:
      self.opportunities["tour_iron_first"] += 1
    return best[2][0]

  def task_action(self, obs):
    inv = obs.inventory
    eligible = (self.forge_return_enabled and not inv.get("diamond", 0)
                and not inv.get("iron_pickaxe", 0)
                and inv.get("stone_pickaxe", 0) and inv.get("stone_sword", 0)
                and inv.get("wood", 0) >= 1
                and self.table is not None and self.furnace is not None)
    if eligible:
      signature = (inv.get("coal", 0) >= 1, inv.get("iron", 0) >= 1)
      if signature != self._tour_inventory:
        self._tour_target, self._tour_retry = None, -1
        self._tour_inventory = signature
      if all(signature):
        distance, parent, common = self.common_forge_cells(obs)
        common = [p for p in common if self.materials.get(p) in WALKABLE]
        if common and self.position not in common:
          target = min((distance[p], p) for p in common)[1]
          old = self.forge.craft if self.forge else None
          if distance.get(old, 10**9) - distance[target] >= 2:
            action = self.follow(self.reconstruct(parent, self.position, target), obs)
            if action:
              self.opportunities["tour_shorter_forge_return"] += 1
              return "tour_return_forge", action
      elif self.tour_enabled:
        if self._tour_target and self.materials.get(self._tour_target) not in {
            m for m in ("coal", "iron") if inv.get(m, 0) < 1}:
          self._tour_target = None
        if self._tour_target is None and self.step >= self._tour_retry:
          self._tour_target = self._plan_tour(obs)
          self._tour_retry = self.step + 16
        if self._tour_target is not None:
          leg = self._leg(self.position, self.facing, self.materials,
                          self._tour_target, inv, harvest=True)
          action = leg[-1][0] if leg and leg[-1] else None
          if action:
            self.opportunities["tour_resource_actions"] += 1
            return "tour_collect_ore", action
          self._tour_target = None
    return super().task_action(obs)


VARIANTS = {
    "baseline": {},
    "food1": {"food_distance": 1},
    "food6": {"food_distance": 6},
    "tour": {"tour": True},
    "food6_tour": {"food_distance": 6, "tour": True},
    "combat": {"combat": True},
    "forge_return": {"forge_return": True},
    "combined": {"food_distance": 6, "forge_return": True, "combat": True},
}


def make_agent(variant):
  if variant == "baseline":
    return CorrectedAgent()
  return OpportunityAgent(**VARIANTS[variant])
