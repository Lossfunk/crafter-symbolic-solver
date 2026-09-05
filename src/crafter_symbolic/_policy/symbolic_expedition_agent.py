"""Isolated substantial symbolic candidates. No simulator or evaluator imports."""
from __future__ import annotations
import heapq
from .symbolic_opportunity_agent import OpportunityAgent
from .heuristic_agent import DIRECTIONS, WALKABLE, add, sub, manhattan, daylight


class ExpeditionAgent(OpportunityAgent):
  def __init__(self, *, provision=False, excursions=False, pocket=False, decoder=None):
    super().__init__(food_distance=6, forge_return=True, combat=True, decoder=decoder)
    self.provision_enabled, self.excursions_enabled, self.pocket_enabled = provision, excursions, pocket
    self.expedition_event = None
    self._provisioning = False
    self._grass_last_examined = {}
    self._farm_pending = None

  def reset(self):
    self.__init__(provision=self.provision_enabled, excursions=self.excursions_enabled,
                  pocket=self.pocket_enabled, decoder=self.decoder)

  def observe(self, obs):
    pending = self._farm_pending
    super().observe(obs)
    if pending is not None and self.last_action == "do" and self.visible_objects.get(pending) == "plant":
      self.score_eat_plant_done = True
      self.opportunities["farm_confirmed_harvests"] += 1
    self._farm_pending = None
    self.expedition_event = None
    for p in self.current_visible_cells:
      if self.materials.get(p) == "grass":
        self._grass_last_examined[p] = self.step

  def logistics_active(self, inv):
    return bool(inv.get("stone_sword") and not inv.get("diamond") and not (
        inv.get("iron_pickaxe") and "diamond" in self.materials.values()))

  def overnight_runway(self, inv):
    """Forecast necessity cost of the public night schedule, not future enemies.

    Assume 12 exposed entry actions and ideal protected sleeping whenever
    energy allows. Metabolism is the public mechanic; add 32 awake actions
    for leaving the chamber and finding the next meal. This is a planning
    estimate, not a certified survival guarantee.
    """
    until_exit = next((d for d in range(1, 301)
                       if daylight(self.step+d) >= .75 and
                       daylight(self.step+d+1) >= daylight(self.step+d)), 300)
    energy, fatigue, equivalent = inv.get("energy", 0), self.fatigue, 0.0
    for tick in range(until_exit):
      asleep = tick >= 12 and energy < 9
      equivalent += .5 if asleep else 1
      fatigue = min(fatigue-1, 0) if asleep else fatigue+1
      if fatigue < -10:
        fatigue, energy = 0, min(9, energy+1)
      elif fatigue > 30:
        fatigue, energy = 0, max(0, energy-1)
    return equivalent + 32

  def survival_action(self, obs):
    inv = obs.inventory
    if self.pocket_enabled and inv.get("diamond") and inv.get("food",0) <= 5:
      plan = self.score_plant_enclosure
      if plan and self.visible_objects.get(plan["target"]) == "plant_ripe":
        decision = self.farm_harvest_action(obs)
        if decision:
          return decision
    if self.provision_enabled and self.logistics_active(inv):
      light = daylight(self.step)
      falling = daylight(self.step+1) < light
      uncommitted = self.shelter is None or self.shelter.stage == "idle"
      if uncommitted and not self.refilling and inv.get("drink",0) >= 4:
        need = self.overnight_runway(inv) if falling and .4 < light <= .75 else 0
        runway = self.awake_food_steps(inv)
        if need and runway < need:
          # A meal is a complete service objective. Nearby observed cows first;
          # otherwise search while there is still daylight/runway to do so.
          action = self.cow_action(obs, max_route_cost=18)
          if action is None:
            action = self.frontier_action(obs, prefer_grass=True)
          if action and action != "noop":
            self.opportunities["provision_actions"] += 1
            self.expedition_event = {"kind": "night_provision", "runway": runway,
                                     "night_and_exit_budget": need}
            return "expedition_night_provision", action
    return super().survival_action(obs)

  def _service_distance(self, sources, inv):
    """Reverse shortest-path costs over the observed map to service stands."""
    distances = {p: 0 for p in sources}
    queue = [(0, p) for p in sources]
    heapq.heapify(queue)
    while queue:
      cost, p = heapq.heappop(queue)
      if distances[p] != cost:
        continue
      edge = self.transition_cost(p, inv)
      if edge is None:
        continue
      for d in DIRECTIONS:
        q = add(p, d)
        if self.transition_cost(q, inv) is None:
          continue
        if cost+edge < distances.get(q, 10**9):
          distances[q] = cost+edge
          heapq.heappush(queue, (cost+edge, q))
    return distances

  def frontier_action(self, obs, prefer_mountain=False, prefer_grass=False):
    if not (self.excursions_enabled and self.logistics_active(obs.inventory)
            and (prefer_grass or obs.inventory.get("iron_pickaxe"))):
      return super().frontier_action(obs, prefer_mountain, prefer_grass)
    inv = obs.inventory
    distance, parent = self.dijkstra(inv)
    grass = {p for p, m in self.materials.items() if m == "grass"}
    # Productive patches, not isolated grass pixels amidst mined mountains.
    patches = {p for p in grass if sum(add(p, (dx,dy)) in grass
               for dx in range(-2,3) for dy in range(-2,3)) >= 12}
    shores = {add(p,d) for p,m in self.materials.items() if m == "water"
              for d in DIRECTIONS if self.materials.get(add(p,d)) in WALKABLE}
    to_water = self._service_distance(shores, inv)
    to_grass = self._service_distance(patches, inv)
    food, drink = self.awake_food_steps(inv), self.awake_drink_steps(inv)
    options = []
    for p,cost in distance.items():
      if p == self.position:
        continue
      unseen = self.new_view_cells(p)
      # Dynamic food evidence can become useful again; static map coverage
      # alone must not permanently disqualify a broad old grazing patch.
      stale = sum(min(1., max(0,self.step-self._grass_last_examined.get(add(p,(dx,dy)),self.step)-100)/400)
                  for dx in range(-4,5) for dy in range(-3,4)
                  if add(p,(dx,dy)) in grass)
      if not unseen and not (prefer_grass and stale >= 6):
        continue
      diamond_value = self.frontier_information_value(unseen, prefer_mountain) if unseen else 0
      grass_support = sum(add(p,(dx,dy)) in grass for dx in range(-3,4) for dy in range(-3,4))/49
      meal_value = len(unseen)*(.15+grass_support) + stale
      food_pressure = 1.0 if prefer_grass else max(0., (110-food)/110)
      utility = ((1-food_pressure)*diamond_value + food_pressure*4*meal_value)
      if utility <= 0:
        continue
      water_return = to_water.get(p, 60)
      food_return = to_grass.get(p, 60)
      # Mining and final facing make distance a lower estimate. Budget a
      # conservative 1.5 multiplier plus a stochastic hunting allowance.
      shortfall = max(0,1.5*(cost+water_return)+8-drink)
      shortfall += max(0,1.5*(cost+food_return)+32-food)
      rank = (cost + .12*water_return + .2*food_pressure*food_return + shortfall) / utility
      options.append((rank, cost, p, water_return, food_return, shortfall))
    if not options:
      return super().frontier_action(obs, prefer_mountain, prefer_grass)
    _, cost, target, water_return, food_return, shortfall = min(options)
    self.opportunities["excursion_frontiers"] += 1
    self.expedition_event = {"kind": "joint_frontier", "target": target,
                             "outbound": cost, "water_return": water_return,
                             "food_patch_return": food_return, "shortfall": shortfall}
    return self.follow(self.reconstruct(parent,self.position,target),obs) or "noop"

  def choose_protected_plant_enclosure(self, obs):
    if not self.pocket_enabled:
      return super().choose_protected_plant_enclosure(obs)
    distance, _ = self.dijkstra(obs.inventory)
    options = []
    durable = {"tree", "stone", "coal", "iron", "diamond"}
    for target in self.current_visible_cells:
      if self.materials.get(target) not in {"grass", "tree"} or target in self.visible_objects:
        continue
      for d in DIRECTIONS:
        access, outer = add(target,d), add(add(target,d),d)
        approach = add(outer,d)
        if any(p not in self.current_visible_cells or self.materials.get(p) not in WALKABLE
               or p in self.visible_objects or p not in distance for p in (access,outer,approach)):
          continue
        if distance[access] > 8:
          continue
        if not all(add(target,side) in self.current_visible_cells and
                   self.materials.get(add(target,side)) in durable
                   for side in DIRECTIONS if side != d):
          continue
        options.append((distance[access]+2*(self.materials[target]=="tree"),target,d,access,outer))
    if not options:
      return None
    _,target,d,access,outer = min(options)
    self.opportunities["natural_farm_pockets"] += 1
    return {"target": target,"access":access,"outer":outer,"direction":d,
            "wall_count":1,"build_directions":[d]}

  def plant_action(self, obs):
    if self.pocket_enabled and not self.score_eat_plant_done:
      if self.score_plant_enclosure is None:
        self.score_plant_enclosure = self.choose_protected_plant_enclosure(obs)
      if self.score_plant_enclosure is not None:
        self.score_protected_plant = True
        return self.protected_plant_action(obs)
    return super().plant_action(obs)

  def protected_plant_action(self, obs):
    plan = self.score_plant_enclosure
    if self.pocket_enabled and plan and self.materials.get(plan["target"]) == "tree":
      return self.interaction_action(obs,plan["target"],"do")
    return super().protected_plant_action(obs)

  def transition_cost(self, position, inventory):
    if self.pocket_enabled and self.score_plant_enclosure and not self.score_eat_plant_done:
      if position in self.protected_plant_boundary() and self.materials.get(position) not in WALKABLE:
        return None
    return super().transition_cost(position, inventory)

  def farm_harvest_action(self, obs):
    plan = self.score_plant_enclosure
    if not plan:
      return None
    inward = (-plan["direction"][0],-plan["direction"][1])
    if self.materials.get(plan["access"]) == "stone":
      if self.position != plan["outer"]:
        action = self.route_to_cell(obs,plan["outer"])
      else:
        action = "do" if self.facing == inward else DIRECTIONS[inward]
      return ("farm_unseal",action) if action else None
    if self.position != plan["access"]:
      action = self.route_to_cell(obs,plan["access"])
      return ("farm_enter",action) if action else None
    action = "do" if self.facing == inward else DIRECTIONS[inward]
    if action == "do":
      self._farm_pending = plan["target"]
      self._food_pending = (plan["target"],obs.inventory.get("food",0))
    return "farm_harvest",action

  def score_task_action(self, obs):
    if self.pocket_enabled and self.score_plant_enclosure and not self.score_eat_plant_done:
      target = self.score_plant_enclosure["target"]
      # Ripeness controls the harvest state, including after opening the seal.
      # The old generic scheduler would otherwise re-seal an opened ripe crop.
      if self.visible_objects.get(target) == "plant_ripe":
        decision = self.farm_harvest_action(obs)
        if decision:
          return decision
    return super().score_task_action(obs)


VARIANTS = {
    "provision": {"provision": True},
    "expedition": {"provision": True, "excursions": True},
    "pocket": {"pocket": True},
}


def make_agent(name):
  return ExpeditionAgent(**VARIANTS[name])
