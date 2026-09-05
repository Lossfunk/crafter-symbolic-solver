"""Diamond-neutral Crafter Score extension of the frozen v7 controller."""

from __future__ import annotations

from .heuristic_agent import (
    DIRECTIONS,
    MOUNTAIN,
    WALKABLE,
    DiamondAgent,
    SymbolicObservation,
    add,
    chebyshev,
    daylight,
    sub,
)


SCORE_GOALS = {
    "collect_sapling",
    "place_plant",
    "make_wood_sword",
    "make_iron_sword",
    "eat_plant",
}


class CrafterScoreAgent(DiamondAgent):
  """Run the frozen diamond policy, then pursue the five zero-rate tasks.

  ``task_action`` delegates exactly to :class:`DiamondAgent` until diamond is
  visible in inventory. Tactical, necessity, and shelter interrupts remain in
  the inherited ``act`` method both before and after that boundary.
  """

  def __init__(
      self, post_pick_iron_sword_cost: int = 0,
      post_pick_iron_sword_after: int = 0,
      post_pick_iron_sword_min_health: int = 0,
      post_pick_iron_sword_min_food_steps: int = 0,
      post_pick_iron_sword_max_forge_return: int = 0,
      score_weapons_first: bool = False,
      score_safe_plant: bool = False,
      score_protected_plant: bool = False,
      score_protected_plant_max_walls: int = 4,
      score_fast_iron_sword_cost: int = 0,
      score_iron_before_wood: bool = False,
      score_plant_first_wait: bool = False,
      systematic_mountain_after: int = 0,
      systematic_mountain_neighbor_weight: int = 4,
      systematic_mountain_persistent: bool = False,
      systematic_mountain_kernel_radius: int = 0,
      systematic_mountain_window: int = 0,
      systematic_mountain_alternating: bool = False,
      systematic_mountain_pair_lookahead: int = 0,
      **kwargs,
  ) -> None:
    super().__init__(**kwargs)
    self.post_pick_iron_sword_cost = post_pick_iron_sword_cost
    self.post_pick_iron_sword_after = post_pick_iron_sword_after
    self.post_pick_iron_sword_min_health = post_pick_iron_sword_min_health
    self.post_pick_iron_sword_min_food_steps = (
        post_pick_iron_sword_min_food_steps)
    self.post_pick_iron_sword_max_forge_return = (
        post_pick_iron_sword_max_forge_return)
    self.score_weapons_first = score_weapons_first
    self.score_safe_plant = score_safe_plant
    self.score_protected_plant = score_protected_plant
    self.score_protected_plant_max_walls = score_protected_plant_max_walls
    self.score_fast_iron_sword_cost = score_fast_iron_sword_cost
    self.score_iron_before_wood = score_iron_before_wood
    self.score_plant_first_wait = score_plant_first_wait
    self.systematic_mountain_after = systematic_mountain_after
    self.systematic_mountain_neighbor_weight = (
        systematic_mountain_neighbor_weight)
    self.systematic_mountain_persistent = systematic_mountain_persistent
    self.systematic_mountain_kernel_radius = systematic_mountain_kernel_radius
    self.systematic_mountain_window = systematic_mountain_window
    self.systematic_mountain_alternating = systematic_mountain_alternating
    self.systematic_mountain_pair_lookahead = (
        systematic_mountain_pair_lookahead)
    self.systematic_mountain_target: tuple[int, int] | None = None
    self.systematic_mountain_target_selections = 0
    self.systematic_mountain_target_commitments = 0
    self.systematic_mountain_target_abandonments = 0
    self.systematic_mountain_pair_selections = 0
    self.systematic_mountain_pair_target_changes = 0
    self._mountain_kernel_cache_step = -1
    self._mountain_kernel_cache: dict[tuple[int, int], float] = {}
    self.post_pick_iron_sword_choice: bool | None = None
    self.post_pick_iron_sword_bound: int | None = None
    self.post_pick_iron_sword_features: dict[str, object] | None = None
    self.post_pick_iron_sword_stability_deferrals = 0
    self.score_phase = False
    self.score_entry_features: dict[str, object] | None = None
    self.score_fast_iron_sword_choice: bool | None = None
    self.score_fast_iron_sword_bound: int | None = None
    self.score_sapling_done = False
    self.score_place_plant_done = False
    self.score_eat_plant_done = False
    self.score_plant_position: tuple[int, int] | None = None
    self.score_plant_target: tuple[
        tuple[int, int], tuple[int, int], tuple[int, int]] | None = None
    self.score_plant_step: int | None = None
    self.score_plant_exposure: int | None = None
    self.score_plant_enclosure: dict[str, object] | None = None
    self.score_plant_seal_position: tuple[int, int] | None = None
    self.score_plant_outer_position: tuple[int, int] | None = None
    self.score_plant_enclosures_started = 0
    self.score_plant_enclosures_sealed = 0
    self.score_grass_attempts = 0

  def systematic_mountain_active(self, prefer_mountain: bool) -> bool:
    active = bool(
        prefer_mountain and self.systematic_mountain_after and
        self.first_iron_pickaxe is not None and
        self.step - self.first_iron_pickaxe >= self.systematic_mountain_after)
    if not active or not self.systematic_mountain_window:
      return active
    phase = (
        self.step - self.first_iron_pickaxe - self.systematic_mountain_after
    ) // self.systematic_mountain_window
    return phase % 2 == 0 if self.systematic_mountain_alternating else phase == 0

  def frontier_information_value(
      self, unseen: list[tuple[int, int]], prefer_mountain: bool,
  ) -> float:
    if (
        not self.systematic_mountain_active(prefer_mountain) or
        self.systematic_mountain_neighbor_weight < 0
    ):
      return super().frontier_information_value(unseen, prefer_mountain)
    if self.systematic_mountain_kernel_radius:
      return sum(self.mountain_kernel_value(cell) for cell in unseen)
    # A hidden cell touching two or three independently observed solid
    # mountain cells is more likely to continue the mountain interior than a
    # cell touching only one.  With the default weight, one neighbor exactly
    # matches v7's old value 5; this extension only distinguishes stronger
    # local evidence that the old binary prior collapsed together.
    return sum(
        1 + self.systematic_mountain_neighbor_weight * sum(
            self.materials.get(add(cell, direction)) in MOUNTAIN
            for direction in DIRECTIONS)
        for cell in unseen)

  def mountain_kernel_value(self, cell: tuple[int, int]) -> float:
    """Estimate mountain support from only the remembered local map.

    Diamond is sampled only inside the smooth mountain process. A single
    observed mountain neighbor is useful, but a broad local patch of mountain
    evidence is stronger and nearby grass/water evidence marks a likely
    boundary. This compact kernel approximates that posterior without fitting
    a model or reconstructing the hidden simplex field.
    """
    if self._mountain_kernel_cache_step != self.step:
      self._mountain_kernel_cache_step = self.step
      self._mountain_kernel_cache.clear()
    cached = self._mountain_kernel_cache.get(cell)
    if cached is not None:
      return cached

    radius = self.systematic_mountain_kernel_radius
    mountain_weight = 0
    surface_weight = 0
    for dx in range(-radius, radius + 1):
      for dy in range(-radius, radius + 1):
        distance = max(abs(dx), abs(dy))
        if not distance or distance > radius:
          continue
        material = self.materials.get(add(cell, (dx, dy)))
        weight = radius + 1 - distance
        # Generated cave/tunnel path and path left by mining both certify that
        # the cell was part of a mountain component. Utilities are ignored
        # because they may have been placed on either surface or cave path.
        if material in MOUNTAIN or material == "path":
          mountain_weight += weight
        elif material in {"grass", "tree", "sand", "water"}:
          surface_weight += weight

    # The radius-sized denominator term is a conservative prior against
    # extrapolating a whole component from one isolated observed cell. With
    # dense interior evidence the multiplier approaches the original maximum
    # of 1 + neighbor_weight; at a mixed boundary it shrinks automatically.
    value = 1.0 + self.systematic_mountain_neighbor_weight * (
        mountain_weight /
        (mountain_weight + surface_weight + radius)
        if mountain_weight else 0.0)
    self._mountain_kernel_cache[cell] = value
    return value

  def frontier_action(
      self, obs: SymbolicObservation, prefer_mountain: bool = False,
      prefer_grass: bool = False,
  ) -> str:
    if (
        self.systematic_mountain_pair_lookahead and
        self.systematic_mountain_active(prefer_mountain)
    ):
      return self.pair_lookahead_frontier_action(
          obs, prefer_mountain, prefer_grass)
    if not (
        self.systematic_mountain_persistent and
        self.systematic_mountain_active(prefer_mountain)
    ):
      return super().frontier_action(obs, prefer_mountain, prefer_grass)

    distance, parent = self.dijkstra(obs.inventory)
    target = self.systematic_mountain_target
    if target is not None:
      valid = (
          target != self.position and target in distance and
          bool(self.new_view_cells(target)) and
          self.near_observed_mountain(target))
      if valid:
        route = self.reconstruct(parent, self.position, target)
        action = self.follow(route, obs)
        if action:
          self.systematic_mountain_target_commitments += 1
          return action
      self.systematic_mountain_target = None
      self.systematic_mountain_target_abandonments += 1

    candidates = []
    for position, cost in distance.items():
      if position == self.position:
        continue
      unseen = self.new_view_cells(position)
      if not unseen:
        continue
      mountain = self.near_observed_mountain(position)
      grass = self.materials.get(position) in {"grass", "sand"}
      tier = 2 * int(prefer_mountain and not mountain)
      tier += int(prefer_grass and not grass)
      vertical = abs(position[1] - self.position[1])
      horizontal = abs(position[0] - self.position[0])
      ratio = cost / self.frontier_information_value(unseen, prefer_mountain)
      cover_tier = 0
      if self.covered_mountain_frontier and obs.inventory.get("iron_pickaxe", 0):
        arrow_stopping_neighbors = sum(
            self.materials.get(add(position, direction)) not in (
                None, *WALKABLE, "water", "lava")
            for direction in DIRECTIONS)
        cover_tier = -min(2, arrow_stopping_neighbors)
      candidates.append((
          tier, cover_tier, ratio, cost, horizontal - vertical, position))
    if not candidates:
      return "noop"
    *_, target = min(candidates)
    self.systematic_mountain_target = target
    self.systematic_mountain_target_selections += 1
    route = self.reconstruct(parent, self.position, target)
    return self.follow(route, obs) or "noop"

  def pair_lookahead_frontier_action(
      self, obs: SymbolicObservation, prefer_mountain: bool,
      prefer_grass: bool,
  ) -> str:
    """Choose the first leg of a posterior-weighted two-viewpoint sweep.

    The ordinary frontier is a one-step submodular approximation: information
    exposed at a single viewpoint divided by route cost.  Here we evaluate a
    small deterministic shortlist of ordered pairs and value the union of
    their crops, so adjacent redundant viewpoints lose to visibility-spaced
    coverage.  Only the first leg is executed; every new observation replans.
    """
    distance, parent = self.dijkstra(obs.inventory)
    records = []
    for position, cost in distance.items():
      if position == self.position:
        continue
      unseen = frozenset(self.new_view_cells(position))
      if not unseen:
        continue
      mountain = self.near_observed_mountain(position)
      grass = self.materials.get(position) in {"grass", "sand"}
      tier = 2 * int(prefer_mountain and not mountain)
      tier += int(prefer_grass and not grass)
      value = sum(self.mountain_kernel_value(cell) for cell in unseen)
      vertical = abs(position[1] - self.position[1])
      horizontal = abs(position[0] - self.position[0])
      records.append({
          "position": position,
          "cost": cost,
          "unseen": unseen,
          "value": value,
          "single_key": (
              tier, cost / max(value, 1e-9), cost,
              horizontal - vertical, position),
      })
    if not records:
      return "noop"

    baseline = min(records, key=lambda record: record["single_key"])
    minimum_tier = min(record["single_key"][0] for record in records)
    records = [
        record for record in records
        if record["single_key"][0] == minimum_tier]
    # The shortlist bound controls computation, not behavior by a fitted state
    # threshold.  Include the best myopic candidates plus coordinate extremes
    # so a long uncovered boundary arc is not absent merely because its first
    # leg is slightly more expensive.
    limit = self.systematic_mountain_pair_lookahead
    shortlist = sorted(records, key=lambda record: record["single_key"])[:limit]
    for key in (
        lambda record: record["position"][0],
        lambda record: -record["position"][0],
        lambda record: record["position"][1],
        lambda record: -record["position"][1],
    ):
      candidate = min(records, key=key)
      if candidate not in shortlist:
        shortlist.append(candidate)

    weights = {
        cell: self.mountain_kernel_value(cell)
        for record in shortlist for cell in record["unseen"]
    }
    choices = []
    for first in shortlist:
      for second in shortlist:
        union = first["unseen"] | second["unseen"]
        value = sum(weights[cell] for cell in union)
        # Manhattan distance is an optimistic inter-leg cost.  Both endpoints
        # are already reachable under the exact remembered-map Dijkstra, and
        # only the exact route to the first endpoint is executed.
        leg = abs(first["position"][0] - second["position"][0]) + abs(
            first["position"][1] - second["position"][1])
        total_cost = first["cost"] + leg
        choices.append((
            total_cost / max(value, 1e-9),
            first["single_key"], -value, second["single_key"],
            first["position"], second["position"],
        ))
    *_, target, _ = min(choices)
    self.systematic_mountain_pair_selections += 1
    if target != baseline["position"]:
      self.systematic_mountain_pair_target_changes += 1
    route = self.reconstruct(parent, self.position, target)
    return self.follow(route, obs) or "noop"

  @property
  def score_goals_complete(self) -> bool:
    inv = self.last_observation.inventory if self.last_observation else {}
    return (
        self.score_sapling_done and self.score_place_plant_done and
        self.score_eat_plant_done and inv.get("wood_sword", 0) > 0 and
        inv.get("iron_sword", 0) > 0)

  def observe(self, obs: SymbolicObservation) -> None:
    super().observe(obs)
    if obs.inventory.get("diamond", 0):
      self.score_phase = True
      if self.score_entry_features is None:
        distance, _, common = self.common_forge_cells(obs)
        self.score_entry_features = {
            "step": self.step,
            "inventory": dict(obs.inventory),
            "health": obs.inventory.get("health", 0),
            "awake_food_steps": self.awake_food_steps(obs.inventory),
            "awake_drink_steps": self.awake_drink_steps(obs.inventory),
            "forge_return_cost": (
                min(distance[position] for position in common)
                if common else None),
            "iron_sword_local_cost_bound": self.iron_sword_local_cost_bound(obs),
        }
    if obs.inventory.get("sapling", 0):
      self.score_sapling_done = True

    # A plant is stationary. Once its remembered cell is visible, absence
    # proves destruction; retain the placement achievement but clear the live
    # maturation plan so a replacement can be grown for ``eat_plant``.
    if (
        self.score_plant_position is not None and
        self.score_plant_position in self.current_visible_cells and
        self.visible_objects.get(self.score_plant_position) not in {
            "plant", "plant_ripe"} and
        not self.score_eat_plant_done
    ):
      self.score_plant_position = None
      self.score_plant_target = None
      self.score_plant_step = None
      self.score_plant_enclosure = None
      self.score_plant_seal_position = None
      self.score_plant_outer_position = None

  def protected_plant_boundary(self) -> set[tuple[int, int]]:
    """Cells reserved as the four walls around the protected plant."""
    if self.score_plant_enclosure is None:
      return set()
    target = self.score_plant_enclosure["target"]
    assert isinstance(target, tuple)
    return {add(target, direction) for direction in DIRECTIONS}

  def resource_action(
      self, obs: SymbolicObservation, material: str,
  ) -> str | None:
    """Do not mine a live protected plant's remembered enclosure."""
    reserved = (
        self.protected_plant_boundary()
        if self.score_protected_plant and not self.score_eat_plant_done else set())
    targets = [
        position for position, value in self.materials.items()
        if value == material and position not in reserved]
    if not targets:
      return None
    route = self.route_to_any(targets, obs.inventory)
    return self.follow(route, obs) if route else None

  def interaction_action(
      self, obs: SymbolicObservation, target: tuple[int, int], action: str,
  ) -> str | None:
    """Route to a walkable neighbor, face ``target``, and interact."""
    distance, parent = self.dijkstra(obs.inventory)
    choices = []
    for direction in DIRECTIONS:
      stand = sub(target, direction)
      if (
          self.materials.get(stand) in WALKABLE and
          stand not in self.visible_objects and stand in distance
      ):
        choices.append((distance[stand], stand, direction))
    if not choices:
      return None
    _, stand, direction = min(choices)
    if self.position != stand:
      route = self.reconstruct(parent, self.position, stand)
      return self.follow(route, obs)
    return action if self.facing == direction else DIRECTIONS[direction]

  def visible_grass_interaction(self, obs: SymbolicObservation) -> str | None:
    """Interact with a currently verified empty grass cell."""
    distance, parent = self.dijkstra(obs.inventory)
    choices = []
    for target, material in self.materials.items():
      if (
          material != "grass" or target not in self.current_visible_cells or
          target in self.visible_objects
      ):
        continue
      for direction in DIRECTIONS:
        stand = sub(target, direction)
        if (
            self.materials.get(stand) in WALKABLE and
            stand not in self.visible_objects and stand in distance
        ):
          choices.append((distance[stand], stand, target, direction))
    if not choices:
      return None
    _, stand, _, direction = min(choices)
    if self.position != stand:
      route = self.reconstruct(parent, self.position, stand)
      return self.follow(route, obs)
    if self.facing != direction:
      return DIRECTIONS[direction]
    self.score_grass_attempts += 1
    return "do"

  def plant_action(self, obs: SymbolicObservation) -> str | None:
    """Place on a frozen visible grass target instead of chasing new coves."""
    distance, parent = self.dijkstra(obs.inventory)
    if self.score_plant_target is not None:
      target, stand, direction = self.score_plant_target
      still_valid = (
          self.materials.get(target) == "grass" and
          target not in self.visible_objects and
          self.materials.get(stand) in WALKABLE and stand in distance and
          stand not in self.visible_objects)
      if not still_valid:
        self.score_plant_target = None
      else:
        if self.position != stand:
          route = self.reconstruct(parent, self.position, stand)
          return self.follow(route, obs)
        if self.facing != direction:
          return DIRECTIONS[direction]
        self.score_place_plant_done = True
        self.score_plant_position = target
        self.score_plant_step = self.step
        self.score_plant_target = None
        return "place_plant"

    choices = []
    for target, material in self.materials.items():
      if (
          material != "grass" or target not in self.current_visible_cells or
          target in self.visible_objects
      ):
        continue
      exposure = sum(
          self.materials.get(add(target, direction)) in WALKABLE
          for direction in DIRECTIONS)
      fully_known = all(
          add(target, direction) in self.materials for direction in DIRECTIONS)
      forge_distance = min(
          chebyshev(target, utility)
          for utility in (self.table, self.furnace)
          if utility is not None
      ) if self.table is not None or self.furnace is not None else 99
      for direction in DIRECTIONS:
        stand = sub(target, direction)
        if (
            self.materials.get(stand) in WALKABLE and
            stand not in self.visible_objects and stand in distance
        ):
          # Freezing the selected target removes the old drift failure, so the
          # safe variant can make enclosure the primary key without endlessly
          # switching to newly observed coves.
          key = (
              (int(not fully_known), exposure, distance[stand], forge_distance)
              if self.score_safe_plant else
              (distance[stand], exposure, forge_distance, int(not fully_known)))
          choices.append((key, stand, target, direction, exposure))
    if not choices:
      return None
    _, stand, target, direction, exposure = min(choices)
    self.score_plant_exposure = exposure
    if self.score_safe_plant:
      self.score_plant_target = (target, stand, direction)
      return self.plant_action(obs)
    # Preserve the higher-yield distance-primary scheduler as the default. Its
    # target may change after a new observation, but the nearest route remains
    # cheap; only the experimental enclosure-primary policy needs commitment
    # to prevent a distant protected target from drifting.
    if self.position != stand:
      route = self.reconstruct(parent, self.position, stand)
      return self.follow(route, obs)
    if self.facing != direction:
      return DIRECTIONS[direction]
    self.score_place_plant_done = True
    self.score_plant_position = target
    self.score_plant_step = self.step
    return "place_plant"

  def choose_protected_plant_enclosure(
      self, obs: SymbolicObservation,
  ) -> dict[str, object] | None:
    """Choose a locally verified natural cove that is cheap to seal.

    The target and every construction cell must be inside the current 9x7
    semantic crop. The sapling is placed immediately, preserving the cheap
    achievement. Any exposed neighbor is then sealed from the cell two steps
    outward; existing solid neighbors serve as free natural walls.
    """
    distance, _ = self.dijkstra(obs.inventory)
    choices = []
    for target, material in self.materials.items():
      if (
          material != "grass" or target not in self.current_visible_cells or
          target in self.visible_objects or target not in distance
      ):
        continue
      neighbors = [add(target, direction) for direction in DIRECTIONS]
      if not all(
          cell in self.current_visible_cells and
          self.materials.get(cell) not in {None, "void"} and
          cell not in self.visible_objects
          for cell in neighbors
      ):
        continue
      for direction in DIRECTIONS:
        access = add(target, direction)
        outer = add(access, direction)
        if (
            self.materials.get(access) not in WALKABLE or
            access not in distance or
            outer not in self.current_visible_cells or
            self.materials.get(outer) not in WALKABLE or
            outer in self.visible_objects or outer not in distance
        ):
          continue
        buildable = WALKABLE | {"water", "lava"}
        build_directions = [
            side for side in DIRECTIONS
            if self.materials.get(add(target, side)) in buildable]
        wall_count = len(build_directions)
        if wall_count > self.score_protected_plant_max_walls:
          continue
        construction_stands = [
            add(add(target, side), side) for side in build_directions]
        construction_approaches = [
            add(stand, side)
            for stand, side in zip(construction_stands, build_directions)]
        if not all(
            stand in self.current_visible_cells and
            self.materials.get(stand) in WALKABLE and
            stand not in self.visible_objects and stand in distance
            for stand in construction_stands + construction_approaches
        ):
          continue
        forge_distance = min(
            (chebyshev(outer, utility)
             for utility in (self.table, self.furnace)
             if utility is not None),
            default=99,
        )
        # Keep the scheduler's distance-first character within the admitted
        # cheap-cove set. Wall count and forge proximity are only tiebreakers.
        key = (distance[access], wall_count, forge_distance, target, direction)
        choices.append((
            key, target, access, outer, direction, wall_count,
            build_directions))
    if not choices:
      return None
    (_, target, access, outer, direction, wall_count,
     build_directions) = min(choices)
    return {
        "target": target,
        "access": access,
        "outer": outer,
        "direction": direction,
        "wall_count": wall_count,
        "build_directions": build_directions,
    }

  def protected_plant_action(self, obs: SymbolicObservation) -> str | None:
    """Plant immediately, then try to seal the cove's exposed neighbors."""
    if self.score_plant_enclosure is None:
      self.score_plant_enclosure = self.choose_protected_plant_enclosure(obs)
      if self.score_plant_enclosure is None:
        return None
      self.score_plant_enclosures_started += 1

    plan = self.score_plant_enclosure
    target = plan["target"]
    access = plan["access"]
    outer = plan["outer"]
    direction = plan["direction"]
    assert isinstance(target, tuple)
    assert isinstance(access, tuple)
    assert isinstance(outer, tuple)
    assert isinstance(direction, tuple)

    buildable = WALKABLE | {"water", "lava"}
    build_directions = plan["build_directions"]
    assert isinstance(build_directions, list)
    unbuilt_directions = [
        side for side in build_directions
        if self.materials.get(add(target, side)) in buildable]
    # Place the sapling before spending any time or stone on protection.
    plant = self.visible_objects.get(target)
    if plant not in {"plant", "plant_ripe"}:
      inward = (-direction[0], -direction[1])
      action = self.place_from_approach(
          obs, outer, access, inward, "place_plant")
      if action == "place_plant":
        self.score_place_plant_done = True
        self.score_plant_position = target
        self.score_plant_step = self.step
        self.score_plant_exposure = int(plan["wall_count"])
      return action

    self.score_place_plant_done = True
    self.score_plant_position = target
    if self.score_plant_step is None:
      self.score_plant_step = self.step

    if obs.inventory.get("stone", 0) < len(unbuilt_directions):
      action = self.resource_action(obs, "stone")
      return action or self.frontier_action(obs, prefer_mountain=True)

    # Seal non-entrance sides first so the final wall always leaves the agent
    # at the remembered outer harvest position.
    ordered = [side for side in unbuilt_directions if side != direction]
    ordered += [side for side in unbuilt_directions if side == direction]
    if ordered:
      side = ordered[0]
      wall = add(target, side)
      stand = add(wall, side)
      approach = add(stand, side)
      if wall in self.visible_objects:
        return "noop"
      inward = (-side[0], -side[1])
      return self.place_from_approach(
          obs, approach, stand, inward, "place_stone")

    self.score_plant_seal_position = access
    self.score_plant_outer_position = outer
    if not plan.get("sealed_recorded"):
      plan["sealed_recorded"] = True
      self.score_plant_enclosures_sealed += 1
    return "noop"

  def protected_plant_harvest_action(
      self, obs: SymbolicObservation,
  ) -> tuple[str, str]:
    """Wait outside the enclosure, unseal it, and eat only when ripe."""
    plan = self.score_plant_enclosure
    if plan is None or self.score_plant_position is None:
      return "score_recover_plant", self.frontier_action(
          obs, prefer_grass=True)
    target = plan["target"]
    access = plan["access"]
    outer = plan["outer"]
    direction = plan["direction"]
    assert isinstance(target, tuple)
    assert isinstance(access, tuple)
    assert isinstance(outer, tuple)
    assert isinstance(direction, tuple)

    ripe = self.visible_objects.get(target) == "plant_ripe"
    if not ripe:
      if self.position != outer:
        action = self.route_to_cell(obs, outer)
        if action:
          return "score_return_to_protected_plant", action
      return "score_grow_protected_plant", "noop"

    inward = (-direction[0], -direction[1])
    if self.materials.get(access) == "stone":
      if self.position != outer:
        action = self.route_to_cell(obs, outer)
        if action:
          return "score_reach_protected_plant", action
      if self.facing != inward:
        return "score_face_plant_seal", DIRECTIONS[inward]
      return "score_unseal_ripe_plant", "do"

    if self.position != access:
      action = self.route_to_cell(obs, access)
      if action:
        return "score_enter_plant_enclosure", action
      return "score_enter_plant_enclosure", "noop"
    if self.facing != inward:
      return "score_face_ripe_plant", DIRECTIONS[inward]
    self.score_eat_plant_done = True
    return "score_eat_plant", "do"

  def score_wood_sword_action(
      self, obs: SymbolicObservation,
  ) -> tuple[str, str]:
    preparation = self.ensure_table(obs, reserve_wood=1)
    if preparation:
      return preparation
    if self.near_utility(self.table):
      return "score_make_wood_sword", "make_wood_sword"
    action = self.route_near_utilities(obs, require_furnace=False)
    return (
        "score_return_for_wood_sword",
        action or self.frontier_action(obs, prefer_grass=True))

  def score_iron_sword_action(
      self, obs: SymbolicObservation,
  ) -> tuple[str, str]:
    preparation = self.ensure_forge_for_iron_sword(obs)
    if preparation:
      return preparation
    if self.near_utility(self.table) and self.near_utility(self.furnace):
      return "score_make_iron_sword", "make_iron_sword"
    action = self.route_near_utilities(obs, require_furnace=True)
    return (
        "score_return_for_iron_sword",
        action or self.frontier_action(obs, prefer_mountain=True))

  def route_near_utilities(
      self, obs: SymbolicObservation, require_furnace: bool,
  ) -> str | None:
    if self.table is None or (require_furnace and self.furnace is None):
      return None
    distance, parent = self.dijkstra(obs.inventory)
    goals = [
        position for position in distance
        if chebyshev(position, self.table) <= 1 and
        (not require_furnace or chebyshev(position, self.furnace) <= 1)
    ]
    if not goals:
      return None
    target = min((distance[position], position) for position in goals)[1]
    if target == self.position:
      return None
    route = self.reconstruct(parent, self.position, target)
    return self.follow(route, obs)

  def resource_or_search(
      self, obs: SymbolicObservation, material: str,
  ) -> tuple[str, str]:
    action = self.resource_action(obs, material)
    if action:
      return f"score_collect_{material}", action
    return (
        f"score_search_{material}",
        self.frontier_action(
            obs,
            prefer_mountain=material in {"stone", "coal", "iron"},
            prefer_grass=material == "tree",
        ),
    )

  def ensure_table(
      self, obs: SymbolicObservation, reserve_wood: int,
  ) -> tuple[str, str] | None:
    inv = obs.inventory
    required_wood = reserve_wood + (2 if self.table is None else 0)
    if inv.get("wood", 0) < required_wood:
      return self.resource_or_search(obs, "tree")
    if self.table is None:
      action = self.forge_action(obs)
      if action:
        return f"score_{action[0]}", action[1]
      return "score_find_table_site", self.frontier_action(obs)
    return None

  def ensure_forge_for_iron_sword(
      self, obs: SymbolicObservation,
  ) -> tuple[str, str] | None:
    inv = obs.inventory
    # A remembered table and furnace must share a reachable craft cell. If
    # not, rebuild a local pair instead of oscillating between them.
    if self.table is not None and self.furnace is not None:
      distance, _ = self.dijkstra(inv)
      common = any(
          chebyshev(position, self.table) <= 1 and
          chebyshev(position, self.furnace) <= 1
          for position in distance)
      if not common:
        self.forge = None
        self.table = None
        self.furnace = None

    required_wood = 1 + (2 if self.table is None else 0)
    if inv.get("wood", 0) < required_wood:
      return self.resource_or_search(obs, "tree")
    required_stone = 4 if self.furnace is None else 0
    if inv.get("stone", 0) < required_stone:
      return self.resource_or_search(obs, "stone")
    if inv.get("coal", 0) < 1:
      return self.resource_or_search(obs, "coal")
    if inv.get("iron", 0) < 1:
      return self.resource_or_search(obs, "iron")
    if self.table is None or self.furnace is None:
      action = self.forge_action(obs)
      if action:
        return f"score_{action[0]}", action[1]
      return "score_find_forge_site", self.frontier_action(obs)
    return None

  def common_forge_cells(
      self, obs: SymbolicObservation,
  ) -> tuple[dict[tuple[int, int], int],
             dict[tuple[int, int], tuple[int, int]],
             list[tuple[int, int]]]:
    """Reachable cells adjacent to both remembered crafting utilities."""
    distance, parent = self.dijkstra(obs.inventory)
    if self.table is None or self.furnace is None:
      return distance, parent, []
    common = [
        position for position in distance
        if chebyshev(position, self.table) <= 1 and
        chebyshev(position, self.furnace) <= 1
    ]
    return distance, parent, common

  def iron_sword_local_cost_bound(
      self, obs: SymbolicObservation,
  ) -> int | None:
    """Conservative local gate for a post-pickaxe iron sword.

    The gate admits only worlds where the intact original forge and every
    missing ingredient are already in symbolic memory and reachable. Summing
    their individual from-current-position costs overestimates some shared
    travel and underestimates the exact tour in others; it is a stable local
    burden proxy, not a hidden-map shortest path.
    """
    distance, _, common = self.common_forge_cells(obs)
    if not common:
      return None
    costs = []
    for item, material in (("wood", "tree"), ("coal", "coal"),
                           ("iron", "iron")):
      if obs.inventory.get(item, 0) >= 1:
        costs.append(0)
        continue
      candidates = [
          distance[position]
          for position, known in self.materials.items()
          if known == material and position in distance
      ]
      if not candidates:
        return None
      costs.append(min(candidates))
    return sum(costs) + min(distance[position] for position in common) + 1

  def post_pick_iron_sword_action(
      self, obs: SymbolicObservation,
  ) -> tuple[str, str] | None:
    """Buy the one-hit weapon only under the frozen local-cost decision."""
    if (
        not self.post_pick_iron_sword_cost or
        not obs.inventory.get("iron_pickaxe", 0) or
        obs.inventory.get("iron_sword", 0) or
        self.first_iron_pickaxe is None or
        self.step - self.first_iron_pickaxe < self.post_pick_iron_sword_after
    ):
      return None

    known_diamond = any(
        material == "diamond" for material in self.materials.values())
    if known_diamond:
      return None

    if (
        obs.inventory.get("health", 0) < self.post_pick_iron_sword_min_health or
        self.awake_food_steps(obs.inventory) <
        self.post_pick_iron_sword_min_food_steps
    ):
      # The Guardian is an investment, not an emergency maneuver. Continue
      # the original policy until ordinary resupply/regeneration creates enough
      # runway; do not freeze the choice while the precondition is false.
      self.post_pick_iron_sword_stability_deferrals += 1
      return None

    if self.post_pick_iron_sword_choice is None:
      bound = self.iron_sword_local_cost_bound(obs)
      self.post_pick_iron_sword_bound = bound
      distance, _, common = self.common_forge_cells(obs)
      nearest = {}
      for material in ("tree", "coal", "iron", "water"):
        costs = [
            distance[position]
            for position, known in self.materials.items()
            if known == material and position in distance
        ]
        nearest[material] = min(costs) if costs else None
      self.post_pick_iron_sword_features = {
          "step": self.step,
          "search_age": self.step - self.first_iron_pickaxe,
          "bound": bound,
          "health": obs.inventory.get("health", 0),
          "food": obs.inventory.get("food", 0),
          "drink": obs.inventory.get("drink", 0),
          "energy": obs.inventory.get("energy", 0),
          "awake_food_steps": self.awake_food_steps(obs.inventory),
          "awake_drink_steps": self.awake_drink_steps(obs.inventory),
          "daylight": daylight(self.step),
          "visible_hostiles": sum(
              name in {"zombie", "skeleton", "arrow"}
              for name in self.visible_objects.values()),
          "mapped_cells": len(self.materials),
          "visited_cells": len(self.visited),
          "known_mountain_cells": sum(
              material in {"stone", "coal", "iron", "diamond"}
              for material in self.materials.values()),
          "known_resources": {
              material: sum(known == material
                            for known in self.materials.values())
              for material in ("tree", "coal", "iron", "diamond")
          },
          "nearest_resource_costs": nearest,
          "forge_return_cost": (
              min(distance[position] for position in common)
              if common else None),
          "shelter_available": self.shelter is not None,
      }
      forge_return_cost = (
          min(distance[position] for position in common) if common else None)
      self.post_pick_iron_sword_choice = (
          bound is not None and bound <= self.post_pick_iron_sword_cost and
          (not self.post_pick_iron_sword_max_forge_return or
           (forge_return_cost is not None and
            forge_return_cost <= self.post_pick_iron_sword_max_forge_return)))
    if not self.post_pick_iron_sword_choice:
      return None

    inv = obs.inventory
    distance, _, _ = self.common_forge_cells(obs)
    missing = []
    for item, material in (("wood", "tree"), ("coal", "coal"),
                           ("iron", "iron")):
      if inv.get(item, 0) >= 1:
        continue
      costs = [
          distance[position]
          for position, known in self.materials.items()
          if known == material and position in distance
      ]
      if costs:
        missing.append((min(costs), material))
    if missing:
      _, material = min(missing)
      return self.resource_or_search(obs, material)

    distance, parent, common = self.common_forge_cells(obs)
    if not common:
      # A later arrow can destroy a utility after the admission decision.
      # Abandon rather than turn a cheap optional purchase into a rebuild.
      self.post_pick_iron_sword_choice = False
      return None
    target = min((distance[position], position) for position in common)[1]
    if target != self.position:
      route = self.reconstruct(parent, self.position, target)
      return "prediamond_return_for_iron_sword", self.follow(route, obs)
    return "prediamond_make_iron_sword", "make_iron_sword"

  def score_task_action(self, obs: SymbolicObservation) -> tuple[str, str]:
    inv = obs.inventory

    if self.score_weapons_first:
      if not inv.get("iron_sword", 0):
        return self.score_iron_sword_action(obs)
      if not inv.get("wood_sword", 0):
        return self.score_wood_sword_action(obs)

    if self.score_fast_iron_sword_cost and not inv.get("iron_sword", 0):
      if self.score_fast_iron_sword_choice is None:
        bound = self.iron_sword_local_cost_bound(obs)
        self.score_fast_iron_sword_bound = bound
        self.score_fast_iron_sword_choice = (
            bound is not None and bound <= self.score_fast_iron_sword_cost)
      if self.score_fast_iron_sword_choice:
        return self.score_iron_sword_action(obs)

    # Bank the two cheapest missing achievements first and start the plant's
    # 300-update clock while the sword tasks are still in progress.
    if not self.score_sapling_done:
      action = self.visible_grass_interaction(obs)
      return (
          "score_collect_sapling", action or
          self.frontier_action(obs, prefer_grass=True))

    if self.score_plant_position is None and not self.score_eat_plant_done:
      if inv.get("sapling", 0) < 1:
        action = self.visible_grass_interaction(obs)
        return (
            "score_recollect_sapling", action or
            self.frontier_action(obs, prefer_grass=True))
      if self.score_protected_plant:
        action = self.protected_plant_action(obs)
        if self.score_plant_enclosure is None:
          action = self.plant_action(obs)
      else:
        action = self.plant_action(obs)
      return (
          "score_place_plant", action or
          self.frontier_action(obs, prefer_grass=True))

    if (
        self.score_protected_plant and not self.score_eat_plant_done and
        self.score_plant_position is not None and
        self.score_plant_enclosure is not None and
        self.materials.get(self.score_plant_enclosure["access"]) != "stone"
    ):
      action = self.protected_plant_action(obs)
      return "score_seal_plant", action or "noop"

    # Once enough wall-clock time has passed, revisit the plant. Actual growth
    # occurs only while it lies inside Crafter's active object-update radius,
    # so elapsed time alone never certifies ripeness; the oracle label must
    # show the distinct visible ripe-plant texture before interaction.
    if (
        not self.score_eat_plant_done and
        self.score_plant_position is not None and
        self.score_plant_step is not None and
        self.step - self.score_plant_step >= 305
    ):
      if self.score_protected_plant and self.score_plant_enclosure is not None:
        return self.protected_plant_harvest_action(obs)
      ripe = self.visible_objects.get(self.score_plant_position) == "plant_ripe"
      action = self.interaction_action(obs, self.score_plant_position, "do")
      if action:
        if (
            ripe and
            abs(self.position[0] - self.score_plant_position[0]) +
            abs(self.position[1] - self.score_plant_position[1]) == 1 and
            action == "do"
        ):
          self.score_eat_plant_done = True
          return "score_eat_plant", action
        if ripe:
          return "score_reach_ripe_plant", action
        # Route back first; once adjacent to a still-unripe plant, wait inside
        # its active radius instead of repeatedly interacting to no effect.
        if abs(self.position[0] - self.score_plant_position[0]) + abs(
            self.position[1] - self.score_plant_position[1]) == 1:
          return "score_grow_plant", "noop"
        return "score_return_to_plant", action
      self.score_plant_position = None
      self.score_plant_step = None
      return "score_recover_plant", self.frontier_action(obs, prefer_grass=True)

    if (
        self.score_plant_first_wait and not self.score_eat_plant_done and
        self.score_plant_position is not None
    ):
      # Keep the plant inside Crafter's active object-update radius instead of
      # leaving it behind during the two sword projects. Inherited survival
      # logic still preempts this task for food, water, sleep, and combat.
      distance, _ = self.dijkstra(inv)
      nearby = [
          position for position in distance
          if chebyshev(position, self.score_plant_position) <= 8]
      if nearby and self.position not in nearby:
        target = min((distance[position], position) for position in nearby)[1]
        action = self.route_to_cell(obs, target)
        if action:
          return "score_return_to_plant_first", action
      return "score_wait_for_plant_first", "noop"

    weapon_order = (
        (("iron_sword", self.score_iron_sword_action),
         ("wood_sword", self.score_wood_sword_action))
        if self.score_iron_before_wood else
        (("wood_sword", self.score_wood_sword_action),
         ("iron_sword", self.score_iron_sword_action))
    )
    for item, action_fn in weapon_order:
      if not inv.get(item, 0):
        return action_fn(obs)

    if not self.score_eat_plant_done and self.score_plant_position is not None:
      # Remain close enough for Plant.update() while inherited survival logic
      # services food, water, energy, and night shelter when necessary.
      distance, _ = self.dijkstra(inv)
      nearby = [
          position for position in distance
          if chebyshev(position, self.score_plant_position) <= 8]
      if nearby and self.position not in nearby:
        target = min((distance[position], position) for position in nearby)[1]
        action = self.route_to_cell(obs, target)
        if action:
          return "score_return_to_growing_plant", action
      return "score_wait_for_plant", "noop"

    return "score_complete", "noop"

  def task_action(self, obs: SymbolicObservation) -> tuple[str, str]:
    if not obs.inventory.get("diamond", 0):
      iron_sword = self.post_pick_iron_sword_action(obs)
      if iron_sword:
        return iron_sword
      return super().task_action(obs)
    self.score_phase = True
    return self.score_task_action(obs)


__all__ = ["CrafterScoreAgent", "SCORE_GOALS"]
