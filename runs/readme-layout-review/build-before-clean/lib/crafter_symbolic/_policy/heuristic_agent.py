"""Contract-safe symbolic Crafter diamond agent.

The agent receives only an ego-relative symbolic decoding of the standard local
crop and displayed inventory. It never receives an environment object, absolute
position, global map, or hidden creature state.
"""

from __future__ import annotations

import collections
import dataclasses
import heapq
import math
from typing import Iterable


DIRECTIONS = {
    (-1, 0): "move_left",
    (1, 0): "move_right",
    (0, -1): "move_up",
    (0, 1): "move_down",
}
ACTION_DIRECTIONS = {action: direction for direction, action in DIRECTIONS.items()}
WALKABLE = {"grass", "path", "sand"}
MOUNTAIN = {"stone", "coal", "iron", "diamond", "lava"}
PLACEABLE = {"grass", "path", "sand"}
HOSTILES = {"zombie", "skeleton"}


def add(a: tuple[int, int], b: tuple[int, int]) -> tuple[int, int]:
  return a[0] + b[0], a[1] + b[1]


def sub(a: tuple[int, int], b: tuple[int, int]) -> tuple[int, int]:
  return a[0] - b[0], a[1] - b[1]


def neg(a: tuple[int, int]) -> tuple[int, int]:
  return -a[0], -a[1]


def manhattan(a: tuple[int, int], b: tuple[int, int]) -> int:
  return abs(a[0] - b[0]) + abs(a[1] - b[1])


def chebyshev(a: tuple[int, int], b: tuple[int, int]) -> int:
  return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def daylight(step: int) -> float:
  progress = (step / 300) % 1 + 0.3
  return 1 - abs(math.cos(math.pi * progress)) ** 3


@dataclasses.dataclass(frozen=True)
class SymbolicObservation:
  """All fields are contract-visible and ego-relative."""

  materials: dict[tuple[int, int], str]
  objects: dict[tuple[int, int], str]
  object_directions: dict[tuple[int, int], tuple[int, int]]
  inventory: dict[str, int]
  facing: tuple[int, int]
  sleeping: bool
  reward: float


@dataclasses.dataclass
class ForgePlan:
  craft: tuple[int, int]
  table_direction: tuple[int, int]
  furnace_direction: tuple[int, int]
  stage: str = "route_table_approach"

  @property
  def table(self) -> tuple[int, int]:
    return add(self.craft, self.table_direction)

  @property
  def table_approach(self) -> tuple[int, int]:
    return sub(self.craft, self.table_direction)

  @property
  def furnace(self) -> tuple[int, int]:
    return add(self.craft, self.furnace_direction)

  @property
  def furnace_approach(self) -> tuple[int, int]:
    return sub(self.craft, self.furnace_direction)


@dataclasses.dataclass
class ShelterPlan:
  stand: tuple[int, int]
  direction: tuple[int, int]
  stage: str = "route"
  built: bool = False
  last_night_mined_cycle: int = -1

  @property
  def first(self) -> tuple[int, int]:
    return add(self.stand, self.direction)

  @property
  def second(self) -> tuple[int, int]:
    return add(self.first, self.direction)

  @property
  def third(self) -> tuple[int, int]:
    return add(self.second, self.direction)


class DiamondAgent:

  def __init__(
      self, craft_stone_sword: bool = False, craft_wood_sword: bool = False,
      shelter_light: float = 0.58,
      food_hunt_level: int = 5, heal_before_exit: int = 0,
      local_shelter: bool = True, shelter_exit_light: float = 0.75,
      prebuild_shelter: bool = False, night_mining: bool = False,
      night_mining_after: int = 0,
      night_mining_reseal: bool = False,
      post_iron_wood_sword: bool = False,
      directed_mountain_frontier: bool = False,
      adaptive_food: bool = False,
      after_first_night_wood_sword: bool = False,
      shelter_combat: bool = False,
      low_health_kite: bool = False,
      opportunistic_wood_sword: bool = False,
      avoid_single_zombie: bool = False,
      low_health_shelter_light: float = 0.0,
      avoid_zombie_clusters: bool = False,
      cheap_wood_sword_cost: int = 0,
      reactive_wood_sword: bool = False,
      finish_known_diamond: bool = False,
      soft_food_hunt_cost: int = 0,
      skip_sword_known_diamond: bool = False,
      focus_damaged_enemy: bool = False,
      drink_seek_level: int = 4,
      cautious_critical_exit: bool = False,
      critical_cluster_retreat: bool = False,
      adaptive_sword_cost: int = 0,
      strike_facing_in_cluster: bool = False,
      avoid_entering_arrow: bool = False,
      avoid_arrow_health: int = 0,
      critical_single_retreat: bool = False,
      food_buffer_steps: int = 0,
      food_search_buffer_steps: int = 0,
      shelter_combat_min_remaining: int = 0,
      conditional_both_health: int = 0,
      zombie_barrier_health: int = 0,
      cluster_escape_health: int = 0,
      engage_lone_zombie_health: int = 0,
      craft_iron_sword: bool = False,
      engage_lone_zombie_needs_gate: bool = False,
      post_iron_shelter_light: float = 0.0,
      cooldown_aware_critical_retreat: bool = False,
      post_iron_food_search_buffer_steps: int = 0,
      forge_search_deadline: int = 0,
      cooldown_certified_cluster_counterattack: bool = False,
      compact_shelter: bool = False,
      deadline_aware_shelter: bool = False,
      natural_corridor_shelter: bool = False,
      covered_mountain_frontier: bool = False,
      threat_aware_routes: bool = False,
      threat_aware_routes_health: int = 0,
      drink_buffer_steps: int = 0,
      emergency_shelter_health: int = 0,
      recent_cow_cost: int = 0,
      stone_reserve: int = 0,
      safe_doorway_exit: bool = False,
      wait_out_zombies: bool = False,
      defer_last_wood: bool = False,
      mobile_workstation_savings: int = 0,
      clear_shelter_pursuer: bool = False,
      defer_last_wood_if_cost_gt: int = 0,
      water_route_margin: int = 0,
      defer_last_wood_if_cost_le: int = 0,
      post_iron_food_search_after_steps: int = 0,
      post_iron_food_search_safe_only: bool = False,
      post_iron_recent_cow_cost: int = 0,
      revalidate_reused_shelter: bool = False,
      certified_shelter_walls: bool = False,
      preseal_shelter_certification: bool = False,
      active_projectile_shelter_guard: bool = False,
      critical_risk_veto: bool = False,
      critical_risk_veto_health: int = 0,
      post_pick_critical_risk_veto_after: int = 0,
      post_pick_critical_risk_veto_health: int = 0,
      post_pick_critical_risk_veto_margin: float = 0.0,
      stationary_lethal_arrow_escape: bool = False,
      bootstrap_mountain_tiebreak: bool = False,
      known_diamond_component_frontier: bool = False,
      known_diamond_component_after: int = 0,
      known_diamond_component_iron_only: bool = False,
      viability_shield_horizon: int = 0,
      viability_shield_shadow: bool = False,
      viability_shield_runway_only: bool = False,
  ) -> None:
    self.craft_stone_sword = craft_stone_sword
    self.craft_wood_sword = craft_wood_sword
    self.shelter_light = shelter_light
    self.food_hunt_level = food_hunt_level
    self.heal_before_exit = heal_before_exit
    self.local_shelter = local_shelter
    self.shelter_exit_light = shelter_exit_light
    self.prebuild_shelter = prebuild_shelter
    self.night_mining = night_mining
    self.night_mining_after = night_mining_after
    self.night_mining_reseal = night_mining_reseal
    self.post_iron_wood_sword = post_iron_wood_sword
    self.directed_mountain_frontier = directed_mountain_frontier
    self.adaptive_food = adaptive_food
    self.after_first_night_wood_sword = after_first_night_wood_sword
    self.shelter_combat = shelter_combat
    self.low_health_kite = low_health_kite
    self.opportunistic_wood_sword = opportunistic_wood_sword
    self.avoid_single_zombie = avoid_single_zombie
    self.low_health_shelter_light = low_health_shelter_light
    self.avoid_zombie_clusters = avoid_zombie_clusters
    self.cheap_wood_sword_cost = cheap_wood_sword_cost
    self.reactive_wood_sword = reactive_wood_sword
    self.finish_known_diamond = finish_known_diamond
    self.soft_food_hunt_cost = soft_food_hunt_cost
    self.skip_sword_known_diamond = skip_sword_known_diamond
    self.focus_damaged_enemy = focus_damaged_enemy
    self.drink_seek_level = drink_seek_level
    self.cautious_critical_exit = cautious_critical_exit
    self.critical_cluster_retreat = critical_cluster_retreat
    self.adaptive_sword_cost = adaptive_sword_cost
    self.strike_facing_in_cluster = strike_facing_in_cluster
    self.avoid_entering_arrow = avoid_entering_arrow
    self.avoid_arrow_health = avoid_arrow_health
    self.critical_single_retreat = critical_single_retreat
    self.food_buffer_steps = food_buffer_steps
    self.food_search_buffer_steps = food_search_buffer_steps
    self.shelter_combat_min_remaining = shelter_combat_min_remaining
    self.conditional_both_health = conditional_both_health
    self.zombie_barrier_health = zombie_barrier_health
    self.cluster_escape_health = cluster_escape_health
    self.engage_lone_zombie_health = engage_lone_zombie_health
    self.craft_iron_sword = craft_iron_sword
    self.engage_lone_zombie_needs_gate = engage_lone_zombie_needs_gate
    self.post_iron_shelter_light = post_iron_shelter_light
    self.cooldown_aware_critical_retreat = cooldown_aware_critical_retreat
    self.post_iron_food_search_buffer_steps = post_iron_food_search_buffer_steps
    self.forge_search_deadline = forge_search_deadline
    self.cooldown_certified_cluster_counterattack = (
        cooldown_certified_cluster_counterattack)
    self.compact_shelter = compact_shelter
    self.deadline_aware_shelter = deadline_aware_shelter
    self.natural_corridor_shelter = natural_corridor_shelter
    self.covered_mountain_frontier = covered_mountain_frontier
    self.threat_aware_routes = threat_aware_routes
    self.threat_aware_routes_health = threat_aware_routes_health
    self.drink_buffer_steps = drink_buffer_steps
    self.emergency_shelter_health = emergency_shelter_health
    self.recent_cow_cost = recent_cow_cost
    self.stone_reserve = stone_reserve
    self.safe_doorway_exit = safe_doorway_exit
    self.wait_out_zombies = wait_out_zombies
    self.defer_last_wood = defer_last_wood
    self.mobile_workstation_savings = mobile_workstation_savings
    self.clear_shelter_pursuer = clear_shelter_pursuer
    self.defer_last_wood_if_cost_gt = defer_last_wood_if_cost_gt
    self.water_route_margin = water_route_margin
    self.defer_last_wood_if_cost_le = defer_last_wood_if_cost_le
    self.post_iron_food_search_after_steps = post_iron_food_search_after_steps
    self.post_iron_food_search_safe_only = post_iron_food_search_safe_only
    self.post_iron_recent_cow_cost = post_iron_recent_cow_cost
    self.revalidate_reused_shelter = revalidate_reused_shelter
    self.certified_shelter_walls = certified_shelter_walls
    self.preseal_shelter_certification = preseal_shelter_certification
    self.active_projectile_shelter_guard = active_projectile_shelter_guard
    self.critical_risk_veto = critical_risk_veto
    self.critical_risk_veto_health = critical_risk_veto_health
    self.post_pick_critical_risk_veto_after = (
        post_pick_critical_risk_veto_after)
    self.post_pick_critical_risk_veto_health = (
        post_pick_critical_risk_veto_health)
    self.post_pick_critical_risk_veto_margin = (
        post_pick_critical_risk_veto_margin)
    self.stationary_lethal_arrow_escape = stationary_lethal_arrow_escape
    self.bootstrap_mountain_tiebreak = bootstrap_mountain_tiebreak
    self.known_diamond_component_frontier = (
        known_diamond_component_frontier)
    self.known_diamond_component_after = known_diamond_component_after
    self.known_diamond_component_iron_only = (
        known_diamond_component_iron_only)
    self.viability_shield_horizon = viability_shield_horizon
    self.viability_shield_shadow = viability_shield_shadow
    self.viability_shield_runway_only = viability_shield_runway_only
    self.position = (0, 0)
    self.facing = (0, 1)
    self.step = 0
    self.last_action: str | None = None
    self.last_observation: SymbolicObservation | None = None
    self.stationary_lethal_arrow_escapes = 0
    self.night_mining_starts = 0
    self.night_mining_reseals = 0
    self.night_mining_reserve_blocks = 0
    self.bootstrap_survey_tie_opportunities = 0
    self.bootstrap_survey_target_changes = 0
    self.bootstrap_survey_route_changes = 0
    self.bootstrap_survey_material_counts: collections.Counter[str] = (
        collections.Counter())
    self.known_diamond_component_frontier_selections = 0
    self.known_diamond_component_frontier_changes = 0
    self.known_diamond_component_frontier_fallbacks = 0
    self.viability_shield_evaluations = 0
    self.viability_shield_suggestions = 0
    self.viability_shield_interventions = 0
    self.viability_shield_suggestion_modes: collections.Counter[str] = (
        collections.Counter())
    self.viability_shield_suggestion_reasons: collections.Counter[str] = (
        collections.Counter())
    self.viability_shield_last_suggestion: dict | None = None
    self._viability_suggestion_reason: str | None = None

    self.materials: dict[tuple[int, int], str] = {}
    self.visible_objects: dict[tuple[int, int], str] = {}
    self.visible_object_directions: dict[tuple[int, int], tuple[int, int]] = {}
    self.last_seen_objects: dict[tuple[int, int], tuple[str, int]] = {}
    self.enemy_damage: dict[tuple[int, int], tuple[str, int]] = {}
    # Contract-safe estimates inferred only from visible motion and health
    # changes. None means that identity/attack attribution became ambiguous.
    self.zombie_cooldowns: dict[tuple[int, int], int | None] = {}
    self.visited = collections.Counter()
    self.last_visit_step: dict[tuple[int, int], int] = {}
    self.observed_count = collections.Counter()

    self.forge: ForgePlan | None = None
    self.table: tuple[int, int] | None = None
    self.furnace: tuple[int, int] | None = None
    self.shelter: ShelterPlan | None = None
    self.refilling = False
    self.mode = "initialize"
    self.mode_counts = collections.Counter()
    self.first_saw_diamond: int | None = None
    self.first_iron_pickaxe: int | None = None
    self.first_iron_pickaxe_features: dict[str, object] | None = None
    self.shelters_built = 0
    self.shelter_sites = 0
    self.shelter_invalidations = 0
    self.shelter_certification_failures = 0
    self.shelter_certification_reasons = collections.Counter()
    self.critical_risk_vetoes = 0
    self.unsafe_shelters: set[
        tuple[tuple[int, int], tuple[int, int]]] = set()
    self.preparing_shelter = False
    self.bridges = 0
    self.recent_positions = collections.deque(maxlen=24)
    self.forage_target: tuple[int, int] | None = None
    self.has_woken = False
    self.close_zombie_encountered = False
    self.adaptive_sword_choice: str | None = None
    self.conditional_both_choice: bool | None = None
    self.cluster_escape_direction: tuple[int, int] | None = None
    self.cluster_escape_steps = 0
    self.emergency_sheltering = False
    self.workstation_relocations = 0
    self.defer_last_wood_choice: bool | None = None
    self.last_wood_decision_features: dict[str, int | bool | None] | None = None
    # Exact half-step metabolic counters reconstructed from action history.
    # Crafter starts all three hidden counters at zero.
    self.hunger_half = 0
    self.thirst_half = 0
    self.fatigue = 0

  # ---------- Observation and belief ----------

  def _commit_previous_action(self) -> None:
    if self.last_action not in ACTION_DIRECTIONS or self.last_observation is None:
      return
    direction = ACTION_DIRECTIONS[self.last_action]
    self.facing = direction
    if self.last_observation.sleeping:
      return
    material = self.last_observation.materials.get(direction, "void")
    obj = self.last_observation.objects.get(direction)
    if obj is None and material in WALKABLE | {"lava"}:
      self.position = add(self.position, direction)

  def _commit_metabolism(self, obs: SymbolicObservation) -> None:
    """Advance the hidden necessity clocks from contract-visible history."""
    if self.last_observation is None or self.last_action is None:
      return
    old = self.last_observation
    energy = old.inventory.get("energy", 0)
    slept_during_update = (
        (old.sleeping and energy < 9) or
        (not old.sleeping and self.last_action == "sleep" and energy < 9))

    # Drinking and a confirmed cow kill reset their corresponding source
    # counter before Crafter applies the current action's life-stat tick.
    target = old.facing
    if (
        self.last_action == "do" and target not in old.objects and
        old.materials.get(target) == "water"
    ):
      self.thirst_half = 0
    if self.last_action == "do" and old.objects.get(target) == "cow":
      one_hit_kill = any(old.inventory.get(name, 0) for name in (
          "stone_sword", "iron_sword"))
      food_increased = obs.inventory.get("food", 0) > old.inventory.get("food", 0)
      if one_hit_kill or food_increased:
        self.hunger_half = 0

    self.hunger_half += 1 if slept_during_update else 2
    if self.hunger_half > 50:
      self.hunger_half = 0
    self.thirst_half += 1 if slept_during_update else 2
    if self.thirst_half > 40:
      self.thirst_half = 0
    if slept_during_update:
      self.fatigue = min(self.fatigue - 1, 0)
      if self.fatigue < -10:
        self.fatigue = 0
    else:
      self.fatigue += 1
      if self.fatigue > 30:
        self.fatigue = 0

  def awake_food_steps(self, inventory: dict[str, int]) -> int:
    food = inventory.get("food", 0)
    if food <= 0:
      return 0
    until_next = (50 - self.hunger_half) // 2 + 1
    return until_next + 26 * (food - 1)

  def awake_drink_steps(self, inventory: dict[str, int]) -> int:
    """Exact awake actions until drink reaches zero without drinking."""
    drink = inventory.get("drink", 0)
    if drink <= 0:
      return 0
    until_next = (40 - self.thirst_half) // 2 + 1
    return until_next + 21 * (drink - 1)

  def observe(self, obs: SymbolicObservation) -> None:
    if (
        self.last_observation is not None and self.last_observation.sleeping and
        not obs.sleeping
    ):
      self.has_woken = True
    self._commit_metabolism(obs)
    self._commit_previous_action()
    self.facing = obs.facing
    self.visited[self.position] += 1
    self.last_visit_step[self.position] = self.step
    self.recent_positions.append(self.position)

    visible = set()
    for offset, material in obs.materials.items():
      absolute = add(self.position, offset)
      visible.add(absolute)
      self.materials[absolute] = material
      self.observed_count[absolute] += 1
      if material == "table":
        self.table = absolute
      elif material == "furnace":
        self.furnace = absolute
      elif material == "diamond" and self.first_saw_diamond is None:
        self.first_saw_diamond = self.step

    if self.table is not None and self.table in visible:
      if self.materials.get(self.table) != "table":
        self.table = None
    if self.furnace is not None and self.furnace in visible:
      if self.materials.get(self.furnace) != "furnace":
        self.furnace = None

    tracked_damage = dict(self.enemy_damage)
    tracked_cooldowns = dict(self.zombie_cooldowns)
    if self.last_action == "do" and self.last_observation is not None:
      old_target = add(self.position, self.last_observation.facing)
      old_name = self.last_observation.objects.get(self.last_observation.facing)
      if old_name in HOSTILES:
        old_damage = tracked_damage.get(old_target, (old_name, 0))[1]
        dealt = max(
            1,
            2 if self.last_observation.inventory.get("wood_sword", 0) else 0,
            3 if self.last_observation.inventory.get("stone_sword", 0) else 0,
            5 if self.last_observation.inventory.get("iron_sword", 0) else 0,
        )
        tracked_damage[old_target] = old_name, old_damage + dealt

    self.visible_objects = {}
    self.visible_object_directions = {}
    self.current_visible_cells = visible
    for offset, name in obs.objects.items():
      absolute = add(self.position, offset)
      self.visible_objects[absolute] = name
      self.last_seen_objects[absolute] = (name, self.step)
    for offset, direction in obs.object_directions.items():
      self.visible_object_directions[add(self.position, offset)] = direction

    new_damage: dict[tuple[int, int], tuple[str, int]] = {}
    new_cooldowns: dict[tuple[int, int], int | None] = {}
    track_candidates = {}
    old_match_counts = collections.Counter()
    for position, name in self.visible_objects.items():
      if name not in HOSTILES:
        continue
      candidates = [
          old_position
          for old_position, (old_name, _) in tracked_damage.items()
          if old_name == name and manhattan(position, old_position) <= 1
      ]
      track_candidates[position] = candidates
      old_match_counts.update(candidates)
    for position, name in self.visible_objects.items():
      if name not in HOSTILES:
        continue
      candidates = track_candidates[position]
      if len(candidates) == 1 and old_match_counts[candidates[0]] == 1:
        old_position = candidates[0]
        damage = tracked_damage[old_position][1]
        new_damage[position] = name, damage
        if name == "zombie":
          cooldown = tracked_cooldowns.get(old_position)
          if cooldown is not None and manhattan(position, self.position) <= 1:
            cooldown = max(0, cooldown - 1)
          new_cooldowns[position] = cooldown
      elif candidates:
        # More than one locally valid bipartite match means physical identity
        # is not observable. Never propagate a positive cooldown across that
        # ambiguity; doing so can certify the wrong cluster member as safe.
        new_damage[position] = name, 0
        if name == "zombie":
          new_cooldowns[position] = None
      else:
        new_damage[position] = name, 0
        if name == "zombie":
          # A never-before-visible zombie cannot previously have attacked the
          # player without having entered the local crop. Its initial cooldown
          # is therefore known to be zero unless this very update hit us.
          new_cooldowns[position] = 0
    self.enemy_damage = new_damage

    if self.last_observation is not None:
      health_loss = max(
          0,
          self.last_observation.inventory.get("health", 0) -
          obs.inventory.get("health", 0),
      )
      adjacent_zombies = [
          position for position, name in self.visible_objects.items()
          if name == "zombie" and manhattan(position, self.position) <= 1]
      arrow_ambiguity = any(
          name == "arrow" for name in self.visible_objects.values()) or any(
              name == "arrow"
              for name in self.last_observation.objects.values())
      necessities_positive = all(
          self.last_observation.inventory.get(name, 0) > 0 and
          obs.inventory.get(name, 0) > 0
          for name in ("food", "drink", "energy"))
      if (
          health_loss == 2 and len(adjacent_zombies) == 1 and
          not arrow_ambiguity and necessities_positive
      ):
        # The observed hit pins this zombie's post-update cooldown at five.
        new_cooldowns[adjacent_zombies[0]] = 5
      elif health_loss and adjacent_zombies:
        # Never manufacture a safe window from ambiguous mixed damage.
        for position in adjacent_zombies:
          new_cooldowns[position] = None
    self.zombie_cooldowns = new_cooldowns

    if any(
        name == "zombie" and manhattan(position, self.position) <= 3
        for position, name in self.visible_objects.items()
    ):
      self.close_zombie_encountered = True

    if obs.inventory.get("iron_pickaxe", 0) and self.first_iron_pickaxe is None:
      self.first_iron_pickaxe = self.step
      self.first_iron_pickaxe_features = self.iron_pickaxe_snapshot(obs)

  def iron_pickaxe_snapshot(self, obs: SymbolicObservation) -> dict[str, object]:
    """Contract-visible state at the first post-bootstrap policy fork.

    This is diagnostic telemetry and a possible input to a future symbolic
    expert selector. It contains no hidden map or environment state.
    """
    distance, _ = self.dijkstra(obs.inventory)
    evidence = {
        position for position, material in self.materials.items()
        if material in MOUNTAIN or material == "path"
    }
    unseen_union: set[tuple[int, int]] = set()
    frontier_count = 0
    mountain_frontier_count = 0
    frontier_costs = []
    mountain_frontier_costs = []
    for position, cost in distance.items():
      if position == self.position:
        continue
      unseen = self.new_view_cells(position)
      if not unseen:
        continue
      frontier_count += 1
      frontier_costs.append(cost)
      unseen_union.update(unseen)
      if self.near_observed_mountain(position):
        mountain_frontier_count += 1
        mountain_frontier_costs.append(cost)

    remaining = set(evidence)
    component_sizes = []
    while remaining:
      start = remaining.pop()
      stack = [start]
      size = 0
      while stack:
        position = stack.pop()
        size += 1
        for direction in DIRECTIONS:
          neighbor = add(position, direction)
          if neighbor in remaining:
            remaining.remove(neighbor)
            stack.append(neighbor)
      component_sizes.append(size)
    component_sizes.sort(reverse=True)

    xs = [position[0] for position in self.materials]
    ys = [position[1] for position in self.materials]
    shelter_distance = None
    if self.shelter is not None:
      shelter_distance = distance.get(self.shelter.stand)
    mountain_material_count = sum(
        material in MOUNTAIN for material in self.materials.values())
    path_count = sum(
        material == "path" for material in self.materials.values())
    surface_count = sum(
        material in {"grass", "tree", "sand", "water"}
        for material in self.materials.values())
    return {
        "step": self.step,
        "health": obs.inventory.get("health", 0),
        "food": obs.inventory.get("food", 0),
        "drink": obs.inventory.get("drink", 0),
        "energy": obs.inventory.get("energy", 0),
        "awake_food_steps": self.awake_food_steps(obs.inventory),
        "awake_drink_steps": self.awake_drink_steps(obs.inventory),
        "daylight": daylight(self.step),
        "mapped_cells": len(self.materials),
        "visited_cells": len(self.visited),
        "map_width": max(xs) - min(xs) + 1,
        "map_height": max(ys) - min(ys) + 1,
        "mountain_material_cells": mountain_material_count,
        "path_cells": path_count,
        "surface_cells": surface_count,
        "mountain_evidence_fraction": (
            len(evidence) / len(self.materials) if self.materials else 0.0),
        "mountain_components": len(component_sizes),
        "largest_mountain_component": component_sizes[0] if component_sizes else 0,
        "second_mountain_component": (
            component_sizes[1] if len(component_sizes) > 1 else 0),
        "frontier_candidates": frontier_count,
        "mountain_frontier_candidates": mountain_frontier_count,
        "unseen_frontier_cells": len(unseen_union),
        "nearest_frontier_cost": min(frontier_costs) if frontier_costs else None,
        "nearest_mountain_frontier_cost": (
            min(mountain_frontier_costs) if mountain_frontier_costs else None),
        "visible_zombies": sum(
            name == "zombie" for name in self.visible_objects.values()),
        "visible_skeletons": sum(
            name == "skeleton" for name in self.visible_objects.values()),
        "visible_arrows": sum(
            name == "arrow" for name in self.visible_objects.values()),
        "known_diamond": any(
            material == "diamond" for material in self.materials.values()),
        "shelter_exists": self.shelter is not None,
        "shelter_built": bool(self.shelter and self.shelter.built),
        "shelter_route_cost": shelter_distance,
        "water_route_cost": self.water_route_cost(obs),
        "shelters_built": self.shelters_built,
        "bridges": self.bridges,
        "has_woken": self.has_woken,
        "close_zombie_encountered": self.close_zombie_encountered,
    }

  # ---------- Mechanics and graph search ----------

  @staticmethod
  def tool_level(inventory: dict[str, int]) -> int:
    if inventory.get("iron_pickaxe", 0):
      return 3
    if inventory.get("stone_pickaxe", 0):
      return 2
    if inventory.get("wood_pickaxe", 0):
      return 1
    return 0

  @staticmethod
  def mineable(material: str, tool: int) -> bool:
    if material == "tree":
      return True
    if material in {"stone", "coal"}:
      return tool >= 1
    if material == "iron":
      return tool >= 2
    if material == "diamond":
      return tool >= 3
    return False

  def transition_cost(
      self, position: tuple[int, int], inventory: dict[str, int],
  ) -> int | None:
    material = self.materials.get(position)
    if material is None or material == "void":
      return None
    if position in self.visible_objects:
      return None
    if material in WALKABLE:
      return 1
    tool = self.tool_level(inventory)
    if self.mineable(material, tool):
      return 2
    if material == "water" and tool >= 1 and inventory.get("stone", 0) >= 1:
      return 3
    # Lava needs an orientation-aware approach macro; it is intentionally not
    # admitted by the generic path planner.
    return None

  def cell_threat_cost(self, position: tuple[int, int]) -> int | None:
    """Conservative local route cost from currently visible hazards."""
    if position in self.arrow_collision_cells():
      return None
    cost = 0
    light = daylight(self.step)
    arrow_walkable = WALKABLE | {"water", "lava"}
    for enemy, name in self.visible_objects.items():
      if name == "zombie":
        distance = manhattan(position, enemy)
        if distance <= 1:
          return None
        if distance == 2:
          cost += 18 if light < 0.65 else 8
        elif distance == 3 and light < 0.5:
          cost += 4
      elif name == "skeleton":
        offset = sub(position, enemy)
        distance = manhattan(position, enemy)
        if distance <= 5 and (offset[0] == 0 or offset[1] == 0):
          direction = (
              0 if offset[0] == 0 else (1 if offset[0] > 0 else -1),
              0 if offset[1] == 0 else (1 if offset[1] > 0 else -1),
          )
          cursor = add(enemy, direction)
          clear = True
          while cursor != position:
            if self.materials.get(cursor) not in arrow_walkable:
              clear = False
              break
            cursor = add(cursor, direction)
          if clear:
            cost += 14
    return cost

  def dijkstra(
      self, inventory: dict[str, int],
  ) -> tuple[dict[tuple[int, int], int], dict[tuple[int, int], tuple[int, int]]]:
    distance = {self.position: 0}
    parent: dict[tuple[int, int], tuple[int, int]] = {}
    queue = [(0, self.position)]
    while queue:
      cost, position = heapq.heappop(queue)
      if distance.get(position) != cost:
        continue
      for direction in DIRECTIONS:
        neighbor = add(position, direction)
        edge = self.transition_cost(neighbor, inventory)
        if edge is None:
          continue
        if (
            self.threat_aware_routes or
            (self.threat_aware_routes_health > 0 and
             inventory.get("health", 0) <= self.threat_aware_routes_health)
        ):
          threat = self.cell_threat_cost(neighbor)
          if threat is None:
            continue
          edge += threat
        candidate = cost + edge
        if candidate < distance.get(neighbor, 10**12):
          distance[neighbor] = candidate
          parent[neighbor] = position
          heapq.heappush(queue, (candidate, neighbor))
    return distance, parent

  def bootstrap_survey_dijkstra(
      self, inventory: dict[str, int],
  ) -> tuple[
      dict[tuple[int, int], int],
      dict[tuple[int, int], tuple[int, int]],
      dict[tuple[int, int], int],
  ]:
    """Shortest paths with a mountain-survey tie-break and no cost slack."""
    distance = {self.position: 0}
    survey = {self.position: 0}
    parent: dict[tuple[int, int], tuple[int, int]] = {}
    queue = [(0, 0, self.position)]
    while queue:
      cost, negative_survey, position = heapq.heappop(queue)
      score = -negative_survey
      if distance.get(position) != cost or survey.get(position) != score:
        continue
      for direction in DIRECTIONS:
        neighbor = add(position, direction)
        edge = self.transition_cost(neighbor, inventory)
        if edge is None:
          continue
        unseen = self.new_view_cells(neighbor)
        supported = sum(
            any(
                self.materials.get(add(cell, offset)) in MOUNTAIN or
                self.materials.get(add(cell, offset)) == "path"
                for offset in DIRECTIONS)
            for cell in unseen)
        # Mountain-supported unknowns dominate generic unknowns. This score is
        # used only after route cost equality has been established.
        candidate_survey = score + 100 * supported + len(unseen)
        candidate_cost = cost + edge
        old = (distance.get(neighbor, 10**12),
               -survey.get(neighbor, -10**12))
        candidate = (candidate_cost, -candidate_survey)
        if candidate < old:
          distance[neighbor] = candidate_cost
          survey[neighbor] = candidate_survey
          parent[neighbor] = position
          heapq.heappush(
              queue, (candidate_cost, -candidate_survey, neighbor))
    return distance, parent, survey

  @staticmethod
  def reconstruct(
      parent: dict[tuple[int, int], tuple[int, int]],
      start: tuple[int, int], target: tuple[int, int],
  ) -> list[tuple[int, int]]:
    route = [target]
    while route[-1] != start:
      if route[-1] not in parent:
        return []
      route.append(parent[route[-1]])
    route.reverse()
    return route

  def route_to_any(
      self, goals: Iterable[tuple[int, int]], inventory: dict[str, int],
  ) -> list[tuple[int, int]]:
    distance, parent = self.dijkstra(inventory)
    choices = [(distance[goal], goal) for goal in goals if goal in distance]
    if not choices:
      return []
    _, target = min(choices)
    return self.reconstruct(parent, self.position, target)

  def follow(self, route: list[tuple[int, int]], obs: SymbolicObservation) -> str | None:
    if len(route) < 2:
      return None
    target = route[1]
    direction = sub(target, self.position)
    material = self.materials.get(target)
    obj = self.visible_objects.get(target)
    if obj is not None:
      return None
    if material in WALKABLE:
      return DIRECTIONS[direction]
    if self.mineable(material, self.tool_level(obs.inventory)):
      return "do" if self.facing == direction else DIRECTIONS[direction]
    if (material == "water" and obs.inventory.get("stone", 0) >= 1 and
        self.tool_level(obs.inventory) >= 1):
      if self.facing != direction:
        return DIRECTIONS[direction]  # Water blocks movement and safely turns.
      self.bridges += 1
      return "place_stone"
    return None

  # ---------- Resource and exploration primitives ----------

  def resource_action(
      self, obs: SymbolicObservation, material: str,
  ) -> str | None:
    targets = [position for position, value in self.materials.items()
               if value == material]
    if not targets:
      return None
    if (
        self.bootstrap_mountain_tiebreak and
        not obs.inventory.get("iron_pickaxe", 0) and
        material in MOUNTAIN
    ):
      baseline_distance, baseline_parent = self.dijkstra(obs.inventory)
      distance, parent, survey = self.bootstrap_survey_dijkstra(obs.inventory)
      choices = [(distance[target], target)
                 for target in targets if target in distance]
      if not choices:
        return None
      minimum = min(cost for cost, _ in choices)
      tied = sorted(target for cost, target in choices if cost == minimum)
      baseline_choices = [
          (baseline_distance[target], target) for target in targets
          if target in baseline_distance]
      baseline_target = min(baseline_choices)[1]
      target = min(tied, key=lambda item: (-survey[item], item))
      baseline_route = self.reconstruct(
          baseline_parent, self.position, baseline_target)
      route = self.reconstruct(parent, self.position, target)
      if route != baseline_route:
        self.bootstrap_survey_tie_opportunities += 1
        self.bootstrap_survey_material_counts[material] += 1
        baseline_action = self.follow(baseline_route, obs)
        survey_action = self.follow(route, obs)
        if survey_action != baseline_action:
          self.bootstrap_survey_route_changes += 1
      if target != baseline_target:
        self.bootstrap_survey_target_changes += 1
      return self.follow(route, obs) if route else None
    route = self.route_to_any(targets, obs.inventory)
    return self.follow(route, obs) if route else None

  def water_action(self, obs: SymbolicObservation) -> str | None:
    targets = [position for position, value in self.materials.items()
               if value == "water"]
    stands = []
    for target in targets:
      for direction in DIRECTIONS:
        stand = sub(target, direction)
        if self.materials.get(stand) in WALKABLE and stand not in self.visible_objects:
          stands.append((stand, target, direction))
    if not stands:
      return None
    distance, parent = self.dijkstra(obs.inventory)
    choices = [(distance[stand], stand, target, direction)
               for stand, target, direction in stands if stand in distance]
    if not choices:
      return None
    _, stand, _, direction = min(choices)
    if self.position != stand:
      route = self.reconstruct(parent, self.position, stand)
      return self.follow(route, obs)
    return "do" if self.facing == direction else DIRECTIONS[direction]

  def water_route_cost(self, obs: SymbolicObservation) -> int | None:
    """Known-map action-cost estimate to the first water interaction."""
    targets = [position for position, value in self.materials.items()
               if value == "water"]
    stands = []
    for target in targets:
      for direction in DIRECTIONS:
        stand = sub(target, direction)
        if self.materials.get(stand) in WALKABLE and stand not in self.visible_objects:
          stands.append(stand)
    if not stands:
      return None
    distance, _ = self.dijkstra(obs.inventory)
    costs = [distance[stand] for stand in stands if stand in distance]
    # At most one action to face the shore, then one `do` resets thirst and
    # adds the first drink. The bound intentionally includes both.
    return min(costs) + 2 if costs else None

  def cow_action(
      self, obs: SymbolicObservation, max_route_cost: int | None = None,
  ) -> str | None:
    cows = [position for position, name in self.visible_objects.items() if name == "cow"]
    if not cows:
      return None
    adjacent = [position for position in cows if manhattan(position, self.position) == 1]
    if adjacent:
      target = min(adjacent)
      direction = sub(target, self.position)
      return "do" if self.facing == direction else DIRECTIONS[direction]
    stands = []
    for cow in cows:
      for direction in DIRECTIONS:
        stand = sub(cow, direction)
        if self.materials.get(stand) in WALKABLE and stand not in self.visible_objects:
          stands.append(stand)
    distance, parent = self.dijkstra(obs.inventory)
    choices = [(distance[stand], stand) for stand in stands if stand in distance]
    if not choices:
      return None
    cost, stand = min(choices)
    if max_route_cost is not None and cost > max_route_cost:
      return None
    route = self.reconstruct(parent, self.position, stand)
    return self.follow(route, obs) if route else None

  def recent_cow_action(
      self, obs: SymbolicObservation, max_route_cost: int,
  ) -> str | None:
    """Cheaply reacquire a cow that just stepped outside the local crop."""
    distance, parent = self.dijkstra(obs.inventory)
    choices = []
    for position, (name, seen_step) in self.last_seen_objects.items():
      if name != "cow" or self.step - seen_step > 12:
        continue
      if position in self.current_visible_cells and position not in self.visible_objects:
        continue
      if position in distance and distance[position] <= max_route_cost:
        choices.append((distance[position], self.step - seen_step, position))
    if not choices:
      return None
    _, _, target = min(choices)
    route = self.reconstruct(parent, self.position, target)
    return self.follow(route, obs) if route else None

  def forage_action(self, obs: SymbolicObservation) -> str:
    """Reacquire moving cows, then explore or patrol productive grass."""
    action = self.cow_action(obs)
    if action:
      self.forage_target = None
      return action

    if self.forage_target == self.position:
      self.forage_target = None
    if self.forage_target is not None:
      action = self.route_to_cell(obs, self.forage_target)
      if action:
        return action
      self.forage_target = None

    recent_cows = [
        (self.step - seen_step, position)
        for position, (name, seen_step) in self.last_seen_objects.items()
        if name == "cow" and self.step - seen_step <= 24
    ]
    if recent_cows:
      _, self.forage_target = min(recent_cows)
      action = self.route_to_cell(obs, self.forage_target)
      if action:
        return action
      self.forage_target = None

    frontier = self.frontier_action(obs, prefer_grass=True)
    if frontier != "noop":
      return frontier

    distance, parent = self.dijkstra(obs.inventory)
    patrol = [
        (self.last_visit_step.get(position, -1), cost, position)
        for position, cost in distance.items()
        if self.materials.get(position) == "grass" and cost >= 4 and
        position not in self.visible_objects
    ]
    if patrol:
      _, _, self.forage_target = min(patrol)
      route = self.reconstruct(parent, self.position, self.forage_target)
      return self.follow(route, obs) or "noop"
    return "noop"

  def new_view_cells(self, position: tuple[int, int]) -> list[tuple[int, int]]:
    return [
        add(position, (dx, dy))
        for dx in range(-4, 5) for dy in range(-3, 4)
        if add(position, (dx, dy)) not in self.materials
    ]

  def near_observed_mountain(self, position: tuple[int, int]) -> bool:
    for known, material in self.materials.items():
      if material in MOUNTAIN and chebyshev(position, known) <= 6:
        return True
    return False

  def known_diamond_component_support(self) -> set[tuple[int, int]]:
    """Candidate viewpoints locally supported by the seen diamond component."""
    evidence = {
        position for position, material in self.materials.items()
        if material in MOUNTAIN or material == "path"
    }
    seeds = {
        position for position, material in self.materials.items()
        if material == "diamond"
    }
    component: set[tuple[int, int]] = set()
    stack = list(seeds)
    while stack:
      position = stack.pop()
      if position in component or position not in evidence:
        continue
      component.add(position)
      stack.extend(add(position, direction) for direction in DIRECTIONS)
    support: set[tuple[int, int]] = set()
    for position in component:
      support.update(
          add(position, (dx, dy))
          for dx in range(-6, 7) for dy in range(-6, 7))
    return support

  def frontier_information_value(
      self, unseen: list[tuple[int, int]], prefer_mountain: bool,
  ) -> int:
    if (
        not prefer_mountain or not self.directed_mountain_frontier or
        self.first_iron_pickaxe is None
    ):
      return len(unseen)
    value = 0
    for cell in unseen:
      near_mountain = any(
          self.materials.get(add(cell, offset)) in MOUNTAIN
          for offset in DIRECTIONS)
      value += 5 if near_mountain else 1
    return value

  def frontier_action(
      self, obs: SymbolicObservation, prefer_mountain: bool = False,
      prefer_grass: bool = False,
  ) -> str:
    distance, parent = self.dijkstra(obs.inventory)
    candidates = []
    baseline_candidates = []
    known_target_active = bool(
        self.known_diamond_component_frontier and prefer_mountain and
        not obs.inventory.get("iron_pickaxe", 0) and
        self.first_saw_diamond is not None and
        self.step - self.first_saw_diamond >=
        self.known_diamond_component_after and
        (
            not self.known_diamond_component_iron_only or
            obs.inventory.get("coal", 0) >= 1
        ))
    known_component_support = (
        self.known_diamond_component_support() if known_target_active else set())
    for position, cost in distance.items():
      if position == self.position:
        continue
      unseen = self.new_view_cells(position)
      if not unseen:
        continue
      mountain = self.near_observed_mountain(position)
      grass = self.materials.get(position) in {"grass", "sand"}
      tier = 0
      if prefer_mountain and not mountain:
        tier += 2
      if prefer_grass and not grass:
        tier += 1
      # Favor actual information per action, then vertical travel because a
      # vertical leading edge exposes nine rather than seven cells.
      vertical = abs(position[1] - self.position[1])
      horizontal = abs(position[0] - self.position[0])
      ratio = cost / self.frontier_information_value(unseen, prefer_mountain)
      cover_tier = 0
      if (
          self.covered_mountain_frontier and prefer_mountain and
          obs.inventory.get("iron_pickaxe", 0)
      ):
        arrow_stopping_neighbors = sum(
            self.materials.get(add(position, direction)) not in (
                None, *WALKABLE, "water", "lava")
            for direction in DIRECTIONS)
        # A candidate with two solid sides is a locally defensible tunnel or
        # choke after entry. Keep the existing information-per-action order
        # within each cover class.
        cover_tier = -min(2, arrow_stopping_neighbors)
      baseline_key = (
          tier, cover_tier, ratio, cost, horizontal - vertical, position)
      baseline_candidates.append(baseline_key)
      known_target_tier = int(
          known_target_active and position not in known_component_support)
      candidates.append((known_target_tier, *baseline_key))
    if not candidates:
      return "noop"
    *_, target = min(candidates)
    if known_target_active:
      self.known_diamond_component_frontier_selections += 1
      baseline_target = min(baseline_candidates)[-1]
      if target != baseline_target:
        self.known_diamond_component_frontier_changes += 1
      if min(candidates)[0]:
        self.known_diamond_component_frontier_fallbacks += 1
    route = self.reconstruct(parent, self.position, target)
    return self.follow(route, obs) or "noop"

  # ---------- Forge primitive ----------

  def choose_forge(self, obs: SymbolicObservation) -> ForgePlan | None:
    distance, _ = self.dijkstra(obs.inventory)
    mountain_cells = [position for position, material in self.materials.items()
                      if material in MOUNTAIN]
    water_cells = [position for position, material in self.materials.items()
                   if material == "water"]
    candidates = []
    perpendicular = {
        (-1, 0): ((0, -1), (0, 1)),
        (1, 0): ((0, -1), (0, 1)),
        (0, -1): ((-1, 0), (1, 0)),
        (0, 1): ((-1, 0), (1, 0)),
    }
    for craft, material in self.materials.items():
      if material not in WALKABLE or craft not in distance:
        continue
      if craft in self.visible_objects:
        continue
      for table_direction in DIRECTIONS:
        for furnace_direction in perpendicular[table_direction]:
          cells = [
              add(craft, table_direction), sub(craft, table_direction),
              add(craft, furnace_direction), sub(craft, furnace_direction),
          ]
          if not all(self.materials.get(cell) in PLACEABLE for cell in cells):
            continue
          if any(cell in self.visible_objects for cell in cells):
            continue
          mountain_distance = min(
              (manhattan(craft, cell) for cell in mountain_cells), default=99)
          water_distance = min(
              (manhattan(craft, cell) for cell in water_cells), default=20)
          # Mountain proximity dominates. Water is a secondary safety tiebreak.
          score = (mountain_distance > 7, mountain_distance, distance[craft], water_distance)
          candidates.append((score, ForgePlan(craft, table_direction, furnace_direction)))
    return min(candidates, key=lambda item: item[0])[1] if candidates else None

  def route_to_cell(self, obs: SymbolicObservation, target: tuple[int, int]) -> str | None:
    route = self.route_to_any([target], obs.inventory)
    return self.follow(route, obs) if route else None

  def place_from_approach(
      self, obs: SymbolicObservation, approach: tuple[int, int],
      stand: tuple[int, int], direction: tuple[int, int], action: str,
  ) -> str | None:
    if self.position == stand and self.facing == direction:
      return action
    if self.position == approach:
      return DIRECTIONS[direction]
    return self.route_to_cell(obs, approach)

  def forge_action(self, obs: SymbolicObservation) -> tuple[str, str] | None:
    if self.forge is None:
      self.forge = self.choose_forge(obs)
      if self.forge is None:
        return None
    plan = self.forge

    if self.table is None:
      action = self.place_from_approach(
          obs, plan.table_approach, plan.craft, plan.table_direction, "place_table")
      if action:
        return "place_table", action
      self.forge = None
      return None

    if self.furnace is None and obs.inventory.get("stone", 0) >= 4:
      action = self.place_from_approach(
          obs, plan.furnace_approach, plan.craft,
          plan.furnace_direction, "place_furnace")
      if action:
        return "place_furnace", action
    return None

  def near_utility(self, position: tuple[int, int] | None) -> bool:
    return position is not None and chebyshev(self.position, position) <= 1

  # ---------- Shelter primitive ----------

  def solid_wall(self, position: tuple[int, int], tool: int) -> bool:
    material = self.materials.get(position)
    return self.mineable(material, tool) and material != "tree"

  def choose_shelter(
      self, obs: SymbolicObservation, max_cost: int = 18,
      min_stone_gain: int = 0,
  ) -> ShelterPlan | None:
    tool = self.tool_level(obs.inventory)
    if tool < 1:
      return None
    distance, _ = self.dijkstra(obs.inventory)
    candidates = []
    for stand, cost in distance.items():
      if cost > max_cost or self.materials.get(stand) not in WALKABLE:
        continue
      for direction in DIRECTIONS:
        if (stand, direction) in self.unsafe_shelters:
          continue
        first = add(stand, direction)
        second = add(first, direction)
        third = add(second, direction)
        required_tunnel = (first, second) if self.compact_shelter else (
            first, second, third)
        strict_tunnel = all(
            self.solid_wall(cell, tool) for cell in required_tunnel)
        if self.natural_corridor_shelter:
          tunnel_valid = all(
              self.materials.get(cell) in WALKABLE or
              self.solid_wall(cell, tool) for cell in required_tunnel)
        else:
          tunnel_valid = strict_tunnel
        if not tunnel_valid:
          continue
        side_a = (-direction[1], direction[0])
        side_b = neg(side_a)
        walls = [add(second, side_a), add(second, side_b), third]
        if not self.compact_shelter:
          walls += [add(third, side_a), add(third, side_b), add(third, direction)]
        certified_wall_materials = (
            MOUNTAIN - {"lava"} if self.certified_shelter_walls else MOUNTAIN)
        strict_walls = all(
            self.materials.get(cell) in certified_wall_materials for cell in walls)
        if self.natural_corridor_shelter:
          walls_valid = all(
              self.materials.get(cell) not in (
                  None, *WALKABLE, "water", "lava") for cell in walls)
        else:
          walls_valid = strict_walls
        if not walls_valid:
          continue
        stone_gain = sum(
            self.materials.get(cell) == "stone" for cell in required_tunnel)
        if stone_gain < min_stone_gain:
          continue
        if obs.inventory.get("stone", 0) + stone_gain < 1:
          continue
        hostile_distance = min(
            (manhattan(stand, enemy) for enemy, name in self.visible_objects.items()
             if name in HOSTILES), default=20)
        # With the extension enabled, preserve every baseline choice whenever
        # any strict excavated-mountain site exists. Natural/mixed corridors
        # are a true fallback rather than a replacement that perturbs already
        # successful shelter trajectories.
        fallback_tier = int(not (strict_tunnel and strict_walls))
        candidates.append((
            (fallback_tier, cost, -hostile_distance),
            ShelterPlan(stand, direction)))
    return min(candidates, key=lambda item: item[0])[1] if candidates else None

  def shelter_boundary_cells(self, plan: ShelterPlan) -> list[tuple[int, int]]:
    """Return the five non-entrance wall cells of a full tunnel shelter."""
    d = plan.direction
    side_a = (-d[1], d[0])
    side_b = neg(side_a)
    walls = [add(plan.second, side_a), add(plan.second, side_b)]
    if self.compact_shelter:
      walls.append(plan.third)
    else:
      walls += [
          add(plan.third, side_a), add(plan.third, side_b), add(plan.third, d)]
    return walls

  def shelter_boundary_intact(self, plan: ShelterPlan) -> bool:
    """Check the remembered creature-proof wall around a reusable chamber.

    Diamond/resource mining can later punch through a previously valid side or
    rear wall. The entrance is intentionally open while an idle shelter is not
    in use, so it is excluded; it will be resealed by the normal state machine.
    """
    wall_materials = (
        MOUNTAIN - {"lava"} if self.certified_shelter_walls else MOUNTAIN)
    return all(
        self.materials.get(cell) in wall_materials
        for cell in self.shelter_boundary_cells(plan))

  def shelter_projectile_boundary_intact(self, plan: ShelterPlan) -> bool:
    """Whether every non-entrance wall stops both creatures and arrows."""
    return all(
        self.materials.get(cell) in MOUNTAIN - {"lava"}
        for cell in self.shelter_boundary_cells(plan))

  def incoming_arrow_ray(self) -> bool:
    """Whether a visible arrow is unobstructedly inbound to this fixed cell."""
    arrow_walkable = WALKABLE | {"water", "lava"}
    for position, name in self.visible_objects.items():
      direction = self.visible_object_directions.get(position)
      if name != "arrow" or direction is None:
        continue
      cursor = position
      for _ in range(10):
        cursor = add(cursor, direction)
        if cursor == self.position:
          return True
        if (
            self.materials.get(cursor) not in arrow_walkable or
            cursor in self.visible_objects
        ):
          break
    return False

  def shelter_action(self, obs: SymbolicObservation) -> tuple[str, str] | None:
    if (
        (self.revalidate_reused_shelter or self.certified_shelter_walls) and
        self.shelter is not None and
        self.shelter.built and
        self.shelter.stage in {"idle", "route_reuse"} and
        not self.shelter_boundary_intact(self.shelter)
    ):
      # Forget the compromised tunnel before re-entering it. A new call to
      # choose_shelter below can select a currently intact local chamber.
      self.shelter = None
      self.shelter_invalidations += 1
    if self.shelter is None:
      self.shelter = self.choose_shelter(obs)
      if self.shelter is None:
        return None
      self.shelter_sites += 1
    elif (
        self.shelter.stage == "idle" and self.local_shelter and
        not self.emergency_sheltering
    ):
      # Exploration can move far from the original chamber. On a later night,
      # compare the cost of returning with excavating the nearest fresh local
      # chamber; a long exposed retreat defeats the purpose of sheltering.
      distance, _ = self.dijkstra(obs.inventory)
      old_cost = distance.get(self.shelter.stand, 10**12)
      candidate = self.choose_shelter(obs)
      if candidate is not None:
        new_cost = distance.get(candidate.stand, 10**12) + 7
        if new_cost < old_cost:
          self.shelter = candidate
          self.shelter_sites += 1
    plan = self.shelter
    d = plan.direction
    reverse = neg(d)

    def enter_action(
        target: tuple[int, int], direction: tuple[int, int], mode: str,
    ) -> tuple[str, str]:
      # Creatures can walk into a tunnel after it is excavated. A protected
      # shelter sequence must clear an occupied next cell instead of issuing
      # the same blocked move forever.
      if target in self.visible_objects:
        action = "do" if self.facing == direction else DIRECTIONS[direction]
        return "shelter_clear", action
      return mode, DIRECTIONS[direction]

    for _ in range(8):
      if plan.stage == "route":
        if self.position == plan.stand:
          plan.stage = "mine_first"
          continue
        action = self.route_to_cell(obs, plan.stand)
        return ("shelter_route", action) if action else None
      if plan.stage == "mine_first":
        if self.materials.get(plan.first) in WALKABLE:
          plan.stage = "enter_first"
          continue
        return "shelter_mine", ("do" if self.facing == d else DIRECTIONS[d])
      if plan.stage == "enter_first":
        if self.position == plan.first:
          plan.stage = "mine_second"
          continue
        return enter_action(plan.first, d, "shelter_enter")
      if plan.stage == "mine_second":
        if self.materials.get(plan.second) in WALKABLE:
          plan.stage = "enter_second"
          continue
        return "shelter_mine", ("do" if self.facing == d else DIRECTIONS[d])
      if plan.stage == "enter_second":
        if self.position == plan.second:
          plan.stage = "seal" if self.compact_shelter else "mine_third"
          continue
        return enter_action(plan.second, d, "shelter_enter")
      if plan.stage == "mine_third":
        if self.materials.get(plan.third) in WALKABLE:
          plan.stage = "enter_third"
          continue
        return "shelter_mine", ("do" if self.facing == d else DIRECTIONS[d])
      if plan.stage == "enter_third":
        if self.position == plan.third:
          plan.stage = "return_second"
          continue
        return enter_action(plan.third, d, "shelter_enter")
      if plan.stage == "return_second":
        if self.position == plan.second:
          plan.stage = "seal"
          continue
        return enter_action(plan.second, reverse, "shelter_turn")
      if plan.stage == "seal":
        if (
            (self.certified_shelter_walls or
             self.preseal_shelter_certification or
             (self.active_projectile_shelter_guard and
              self.incoming_arrow_ray())) and
            not self.shelter_projectile_boundary_intact(plan)
        ):
          # Shelter selection is based on remembered terrain, but the route to
          # its stand can subsequently mine through one of those remembered
          # walls. The zero-stone resupply path can do the same deliberately.
          # Before sealing the only exit and eventually sleeping, require the
          # five side/rear cells to be solid to both creatures and arrows.
          # Lava is therefore rejected even though zombies cannot cross it.
          self.unsafe_shelters.add((plan.stand, plan.direction))
          self.shelter_certification_reasons.update(
              str(self.materials.get(cell, "unknown"))
              for cell in self.shelter_boundary_cells(plan)
              if self.materials.get(cell) not in MOUNTAIN - {"lava"})
          self.shelter = None
          self.preparing_shelter = False
          self.shelter_certification_failures += 1
          return None
        if self.preparing_shelter:
          plan.stage = "prepare_exit_first"
          continue
        if self.materials.get(plan.first) == "stone":
          plan.stage = "sheltered"
          plan.built = True
          self.shelters_built += 1
          continue
        if plan.first in self.visible_objects:
          return "shelter_clear", ("do" if self.facing == reverse else DIRECTIONS[reverse])
        if obs.inventory.get("stone", 0) < 1:
          # A reused shelter's original seal was mined back into inventory on
          # exit, but that stone can later be spent on a bridge. Never loop on
          # an impossible place_stone. Step into the protected rear cell and
          # mine one *known stone* from its enclosed mountain boundary first.
          plan.stage = (
              "compact_seal_resupply_mine" if self.compact_shelter else
              "seal_resupply_enter_third")
          continue
        if self.facing != reverse:
          return "shelter_turn", DIRECTIONS[reverse]
        return "shelter_seal", "place_stone"
      if plan.stage == "compact_seal_resupply_mine":
        if obs.inventory.get("stone", 0) >= 1:
          plan.stage = "seal"
          continue
        candidates = [
            direction for direction in DIRECTIONS
            if direction != reverse and
            self.materials.get(add(plan.second, direction)) == "stone" and
            add(plan.second, direction) not in self.visible_objects
        ]
        if not candidates:
          self.shelter = None
          self.preparing_shelter = False
          return None
        direction = min(candidates)
        action = "do" if self.facing == direction else DIRECTIONS[direction]
        return "shelter_resupply_mine", action
      if plan.stage == "seal_resupply_enter_third":
        if self.position == plan.third:
          plan.stage = "seal_resupply_mine"
          continue
        return enter_action(plan.third, d, "shelter_resupply_enter")
      if plan.stage == "seal_resupply_mine":
        if obs.inventory.get("stone", 0) >= 1:
          plan.stage = "seal_resupply_return_second"
          continue
        candidates = [
            direction for direction in DIRECTIONS
            if direction != reverse and
            self.materials.get(add(plan.third, direction)) == "stone" and
            add(plan.third, direction) not in self.visible_objects
        ]
        if not candidates:
          # The verified boundary can contain ore/lava instead of ordinary
          # stone. Leave unsealed rather than deadlock; the next policy cycle
          # may select a different chamber.
          self.shelter = None
          self.preparing_shelter = False
          return None
        direction = min(candidates)
        action = "do" if self.facing == direction else DIRECTIONS[direction]
        return "shelter_resupply_mine", action
      if plan.stage == "seal_resupply_return_second":
        if self.position == plan.second:
          plan.stage = "seal"
          continue
        return enter_action(plan.second, reverse, "shelter_resupply_return")
      if plan.stage == "prepare_exit_first":
        if self.position == plan.first:
          plan.stage = "prepare_exit_stand"
          continue
        return enter_action(plan.first, reverse, "shelter_prepare_exit")
      if plan.stage == "prepare_exit_stand":
        if self.position == plan.stand:
          plan.stage = "idle"
          self.preparing_shelter = False
          return None
        return enter_action(plan.stand, reverse, "shelter_prepare_exit")
      if plan.stage == "sheltered":
        light = daylight(self.step)
        rising = daylight(self.step + 1) >= light
        visible_hostile = any(name in HOSTILES for name in self.visible_objects.values())
        if self.emergency_sheltering:
          # An already-built dead-end tunnel is a deterministic one-cell
          # ingress and a place to recover.  Leave only after restoring a
          # two-hit health buffer or before necessities become critical.
          emergency_done = (
              obs.inventory.get("health", 0) >= 7 or
              obs.inventory.get("food", 0) <= 2 or
              obs.inventory.get("drink", 0) <= 2)
          if emergency_done:
            self.emergency_sheltering = False
            plan.stage = "unseal"
            continue
          if obs.inventory.get("energy", 0) < 9:
            return "emergency_shelter_sleep", "sleep"
          return "emergency_shelter_wait", "noop"
        critical_needs = obs.inventory.get("food", 0) <= 1
        if self.safe_doorway_exit:
          critical_needs = critical_needs or obs.inventory.get("drink", 0) <= 1
        close_hostile = any(
            name in HOSTILES and manhattan(position, self.position) <= 3
            for position, name in self.visible_objects.items())
        low_food_exit = (
            (critical_needs if self.safe_doorway_exit else
             obs.inventory.get("food", 0) <= 1) and
            rising and light >= 0.45)
        if self.cautious_critical_exit:
          low_food_exit = critical_needs and rising and light >= 0.45
          if close_hostile and obs.inventory.get("health", 0) >= 7:
            # A sealed chamber buys many deprivation ticks. Do not spend that
            # buffer by opening directly into a locally visible dawn cluster;
            # ordinary/forced daylight exits still guarantee eventual exit.
            # Below seven health that buffer is too small to justify waiting.
            low_food_exit = False
        forced_exit_safe = light >= 0.95
        if self.wait_out_zombies:
          forced_exit_safe = forced_exit_safe and not any(
              name == "zombie" for name in self.visible_objects.values())
        if self.safe_doorway_exit:
          visible_zombies = sum(
              name == "zombie" for name in self.visible_objects.values())
          survivable_fresh_hits = max(0, (obs.inventory.get("health", 0) - 1) // 2)
          forced_exit_safe = forced_exit_safe and visible_zombies <= survivable_fresh_hits
        normal_exit = rising and (
            (light >= self.shelter_exit_light and not visible_hostile) or
            forced_exit_safe)
        healthy_enough = obs.inventory.get("health", 0) >= self.heal_before_exit
        if low_food_exit or (normal_exit and healthy_enough):
          plan.stage = "unseal"
          continue
        if obs.inventory.get("energy", 0) < 9:
          return "shelter_sleep", "sleep"
        cycle = self.step // 300
        if (
            self.night_mining and obs.inventory.get("iron_pickaxe", 0) and
            (
                not self.night_mining_after or
                (
                    self.first_iron_pickaxe is not None and
                    self.step - self.first_iron_pickaxe >=
                    self.night_mining_after
                )
            ) and
            plan.last_night_mined_cycle != cycle and
            obs.inventory.get("food", 0) >= 3 and
            obs.inventory.get("drink", 0) >= 4 and
            (
                not self.night_mining_reseal or
                obs.inventory.get("stone", 0) >= 1
            )
        ):
          plan.last_night_mined_cycle = cycle
          self.night_mining_starts += 1
          plan.stage = "night_mine_out"
          continue
        if (
            self.night_mining and self.night_mining_reseal and
            obs.inventory.get("iron_pickaxe", 0) and
            plan.last_night_mined_cycle != cycle and
            obs.inventory.get("food", 0) >= 3 and
            obs.inventory.get("drink", 0) >= 4 and
            obs.inventory.get("stone", 0) < 1
        ):
          # A rear tunnel is useful only if the chamber remains a chamber.
          # Reserve one stone before starting so every sortie can restore the
          # rear wall before the agent sleeps again.
          self.night_mining_reserve_blocks += 1
        return "shelter_wait", "noop"
      if plan.stage == "night_mine_out":
        depth = (
            (self.position[0] - plan.second[0]) * d[0] +
            (self.position[1] - plan.second[1]) * d[1])
        light = daylight(self.step)
        rising = daylight(self.step + 1) >= light
        local_danger = any(
            name in HOSTILES | {"arrow"} for name in self.visible_objects.values())
        if depth >= 7 or (rising and light >= 0.55) or local_danger:
          plan.stage = "night_mine_return"
          continue
        target = add(self.position, d)
        material = self.materials.get(target)
        if target in self.visible_objects:
          return enter_action(target, d, "shelter_night_clear")
        if material in WALKABLE:
          return "shelter_night_move", DIRECTIONS[d]
        if self.mineable(material, self.tool_level(obs.inventory)):
          action = "do" if self.facing == d else DIRECTIONS[d]
          return "shelter_night_mine", action
        plan.stage = "night_mine_return"
        continue
      if plan.stage == "night_mine_return":
        if self.position == plan.second:
          plan.stage = (
              "night_mine_reseal" if self.night_mining_reseal else
              "sheltered")
          continue
        target = add(self.position, reverse)
        return enter_action(target, reverse, "shelter_night_return")
      if plan.stage == "night_mine_reseal":
        # The mining ray starts by removing the shelter's rear wall at third.
        # Restore that wall before resuming sleep; otherwise the nominally
        # sealed state has a creature- and projectile-accessible back door.
        # Use the current local cell rather than the global dead-reckoned map:
        # blocked movement during the sortie can make the latter lag reality.
        if obs.materials.get(d) not in WALKABLE:
          plan.stage = "sheltered"
          self.night_mining_reseals += 1
          continue
        if d in obs.objects:
          action = "do" if self.facing == d else DIRECTIONS[d]
          return "shelter_night_reseal_clear", action
        if obs.inventory.get("stone", 0) < 1:
          # This should be unreachable because the sortie reserves one stone.
          # Stay awake rather than silently treating a breached chamber as
          # safe; the ordinary dawn exit condition will eventually fire.
          return "shelter_night_reseal_wait", "noop"
        if self.facing != d:
          return "shelter_night_reseal_turn", DIRECTIONS[d]
        return "shelter_night_reseal", "place_stone"
      if plan.stage == "unseal":
        if self.materials.get(plan.first) in WALKABLE:
          plan.stage = "exit_first"
          continue
        if self.facing != reverse:
          return "shelter_turn", DIRECTIONS[reverse]
        return "shelter_unseal", "do"
      if plan.stage == "exit_first":
        if self.position == plan.first:
          plan.stage = "exit_stand"
          continue
        if (
            self.safe_doorway_exit and
            self.materials.get(plan.first) in WALKABLE and
            plan.first not in self.visible_objects and
            any(name == "zombie" for name in self.visible_objects.values())
        ):
          # Stay in the inner tunnel cell while the doorway is empty. A zombie
          # can then occupy only the single entrance cell, where the ordinary
          # occupied-cell branch below dispatches it before we reconsider exit.
          return "shelter_door_wait", "noop"
        return enter_action(plan.first, reverse, "shelter_exit")
      if plan.stage == "exit_stand":
        if self.position == plan.stand:
          plan.stage = "idle"
          self.emergency_sheltering = False
          return None
        return enter_action(plan.stand, reverse, "shelter_exit")
      if plan.stage == "idle":
        # Re-enter the existing tunnel from the remembered outer stand.
        plan.stage = "route_reuse"
        continue
      if plan.stage == "route_reuse":
        if self.position == plan.stand:
          plan.stage = "enter_reuse_first"
          continue
        action = self.route_to_cell(obs, plan.stand)
        return ("shelter_route", action) if action else None
      if plan.stage == "enter_reuse_first":
        if self.position == plan.first:
          plan.stage = "enter_reuse_second"
          continue
        return enter_action(plan.first, d, "shelter_enter")
      if plan.stage == "enter_reuse_second":
        if self.position == plan.second:
          plan.stage = "seal" if self.compact_shelter else "enter_reuse_third"
          continue
        return enter_action(plan.second, d, "shelter_enter")
      if plan.stage == "enter_reuse_third":
        if self.position == plan.third:
          plan.stage = "return_reuse_second"
          continue
        return enter_action(plan.third, d, "shelter_enter")
      if plan.stage == "return_reuse_second":
        if self.position == plan.second:
          plan.stage = "seal"
          continue
        return enter_action(plan.second, reverse, "shelter_turn")
    return None

  # ---------- Reactive safety ----------

  def legal_safe_moves(self, obs: SymbolicObservation) -> list[tuple[str, tuple[int, int]]]:
    moves = [("noop", self.position)]
    for direction, action in DIRECTIONS.items():
      target = add(self.position, direction)
      if self.materials.get(target) in WALKABLE and target not in self.visible_objects:
        moves.append((action, target))
    return moves

  def arrow_collision_cells(self) -> set[tuple[int, int]]:
    cells = set()
    arrow_walkable = WALKABLE | {"water", "lava"}
    for position, name in self.visible_objects.items():
      if name != "arrow" or position not in self.visible_object_directions:
        continue
      target = add(position, self.visible_object_directions[position])
      if self.materials.get(target) in arrow_walkable:
        cells.add(target)
    return cells

  def zombie_attack_probability(
      self, zombie: tuple[int, int], player: tuple[int, int],
  ) -> float:
    """Local one-update attack probability under Crafter's zombie policy.

    This freezes other objects at their currently visible cells, so it is a
    tactical estimate rather than simulator lookahead. Positive cooldowns are
    handled by the caller; an off-cooldown zombie moves before attacking.
    """
    offset = sub(player, zombie)
    dx, dy = offset

    def axis_direction(long_axis: bool) -> tuple[int, int]:
      horizontal = abs(dx) > abs(dy) if long_axis else abs(dx) <= abs(dy)
      if horizontal:
        return (0 if dx == 0 else (1 if dx > 0 else -1), 0)
      return (0, 0 if dy == 0 else (1 if dy > 0 else -1))

    probabilities = collections.Counter()
    if manhattan(zombie, player) <= 8:
      probabilities[axis_direction(True)] += 0.72
      probabilities[axis_direction(False)] += 0.18
      for direction in DIRECTIONS:
        probabilities[direction] += 0.025
    else:
      for direction in DIRECTIONS:
        probabilities[direction] += 0.25

    attack = 0.0
    for direction, probability in probabilities.items():
      target = add(zombie, direction)
      move_succeeds = (
          direction != (0, 0) and target != player and
          self.materials.get(target) in WALKABLE and
          target not in self.visible_objects)
      final = target if move_succeeds else zombie
      if manhattan(final, player) <= 1:
        attack += probability
    return attack

  def critical_escape_action(
      self, obs: SymbolicObservation, proposed_action: str,
  ) -> str | None:
    """Veto a strictly riskier action at one-hit health using visible state."""
    base_health_threshold = (
        self.critical_risk_veto_health or (2 if self.critical_risk_veto else 0))
    post_pick_extended = bool(
        self.post_pick_critical_risk_veto_after and
        self.first_iron_pickaxe is not None and
        self.step - self.first_iron_pickaxe >=
        self.post_pick_critical_risk_veto_after)
    health_threshold = max(
        base_health_threshold,
        self.post_pick_critical_risk_veto_health if post_pick_extended else 0)
    if health_threshold <= 0 or obs.inventory.get("health", 0) > health_threshold:
      return None
    required_margin = (
        self.post_pick_critical_risk_veto_margin
        if post_pick_extended and
        obs.inventory.get("health", 0) > base_health_threshold else 0.0)
    zombies = [
        position for position, name in self.visible_objects.items()
        if name == "zombie"]
    arrows = self.arrow_collision_cells()
    if not zombies and not arrows:
      return None

    def projected(action: str) -> tuple[int, int]:
      direction = ACTION_DIRECTIONS.get(action)
      if direction is None:
        return self.position
      target = add(self.position, direction)
      if (
          self.materials.get(target) in WALKABLE and
          target not in self.visible_objects
      ):
        return target
      return self.position

    def score(action: str, target: tuple[int, int]) -> tuple[float, int, int, int]:
      if target in arrows:
        risk = 1.0
      else:
        survival = 1.0
        for zombie in zombies:
          cooldown = self.zombie_cooldowns.get(zombie)
          if cooldown is not None and cooldown > 0:
            continue
          survival *= 1.0 - self.zombie_attack_probability(zombie, target)
        risk = 1.0 - survival
      distances = [manhattan(target, zombie) for zombie in zombies]
      return (
          risk,
          sum(distance <= 1 for distance in distances),
          sum(distance <= 2 for distance in distances),
          -min(distances, default=20),
      )

    proposed_target = projected(proposed_action)
    proposed_score = score(proposed_action, proposed_target)
    candidates = []
    for action, target in self.legal_safe_moves(obs):
      candidate_score = score(action, target)
      candidates.append((
          candidate_score, action != proposed_action, action != "noop",
          self.visited[target], action))
    if not candidates:
      return None
    best = min(candidates)
    if best[0][0] + required_margin + 1e-9 < proposed_score[0]:
      return best[-1]
    return None

  def projected_arrow_cells(
      self, horizon: int,
  ) -> list[set[tuple[int, int]]]:
    """Exact visible-arrow collision cells for subsequent local updates."""
    active = [
        (position, self.visible_object_directions[position])
        for position, name in self.visible_objects.items()
        if name == "arrow" and position in self.visible_object_directions
    ]
    collisions: list[set[tuple[int, int]]] = []
    arrow_walkable = WALKABLE | {"water", "lava"}
    for _ in range(horizon):
      next_active = []
      cells = set()
      for position, direction in active:
        target = add(position, direction)
        if self.materials.get(target) in arrow_walkable:
          cells.add(target)
          next_active.append((target, direction))
      collisions.append(cells)
      active = next_active
    return collisions

  def viability_escape_action(
      self, obs: SymbolicObservation, proposed_action: str,
  ) -> str | None:
    """Prefer an equally immediate-safe move with a longer local escape ray.

    This is a deliberately small, observation-only lookahead.  Zombies are
    granted one cell of adversarial reach per update; the player enumerates
    known-free moves for a few updates.  Exact visible-arrow motion is a hard
    constraint.  Expected one-update zombie risk remains the primary key, so
    the runway term only resolves locally comparable immediate choices.
    """
    horizon = self.viability_shield_horizon
    if horizon <= 1 or obs.inventory.get("health", 0) > 2:
      return None
    zombies = [
        position for position, name in self.visible_objects.items()
        if name == "zombie"]
    arrow_cells = self.projected_arrow_cells(horizon)
    if not zombies and not any(arrow_cells):
      return None
    # Do not break a certified cooldown attack window: unlike geometric
    # runway, the positive cooldown belief has already been validated against
    # the hidden simulator as a conservative safety certificate.
    facing_target = add(self.position, self.facing)
    if (
        proposed_action == "do" and
        self.visible_objects.get(facing_target) == "zombie" and
        (self.zombie_cooldowns.get(facing_target) or 0) > 0
    ):
      return None

    def projected(action: str) -> tuple[int, int]:
      direction = ACTION_DIRECTIONS.get(action)
      if direction is None:
        return self.position
      target = add(self.position, direction)
      if (
          self.materials.get(target) in WALKABLE and
          target not in self.visible_objects
      ):
        return target
      return self.position

    def immediate_risk(target: tuple[int, int]) -> float:
      if target in arrow_cells[0]:
        return 1.0
      survival = 1.0
      for zombie in zombies:
        cooldown = self.zombie_cooldowns.get(zombie)
        if cooldown is not None and cooldown > 0:
          continue
        survival *= 1.0 - self.zombie_attack_probability(zombie, target)
      return 1.0 - survival

    # Retain the proposed non-movement action as the representative for the
    # current cell, so a tie never replaces an attack/interaction with noop.
    first_actions: dict[tuple[int, int], str] = {
        projected(proposed_action): proposed_action}
    for action, target in self.legal_safe_moves(obs):
      first_actions.setdefault(target, action)

    def continuations(position: tuple[int, int]) -> list[tuple[int, int]]:
      cells = [position]
      for direction in DIRECTIONS:
        target = add(position, direction)
        if (
            self.materials.get(target) in WALKABLE and
            target not in self.visible_objects
        ):
          cells.append(target)
      return cells

    def best_runway(first: tuple[int, int]) -> tuple[int, int, int]:
      # Each tuple stores (minimum adversarial clearance, total clearance,
      # negative revisits).  Beam deduplication by (time, position) is exact
      # for this Markov score because only the best prefix at a cell matters.
      initial_clearance = min(
          (manhattan(first, zombie) - 1 for zombie in zombies), default=20)
      if first in arrow_cells[0]:
        initial_clearance = -100
      states = {first: (initial_clearance, initial_clearance,
                        -self.visited[first])}
      for elapsed in range(2, horizon + 1):
        next_states: dict[tuple[int, int], tuple[int, int, int]] = {}
        for position, prefix in states.items():
          for target in continuations(position):
            clearance = min(
                (manhattan(target, zombie) - elapsed for zombie in zombies),
                default=20)
            if target in arrow_cells[elapsed - 1]:
              clearance = -100
            score = (
                min(prefix[0], clearance),
                prefix[1] + clearance,
                prefix[2] - self.visited[target],
            )
            if score > next_states.get(target, (-1000, -1000, -1000)):
              next_states[target] = score
        states = next_states
      return max(states.values(), default=(-1000, -1000, -1000))

    ranked = []
    proposed_target = projected(proposed_action)
    for target, action in first_actions.items():
      runway = best_runway(target)
      ranked.append((
          immediate_risk(target), -runway[0], -runway[1], -runway[2],
          target != proposed_target, action != proposed_action, action))
    proposed = next(item for item in ranked if item[-1] == proposed_action)
    best = min(ranked)
    self.viability_shield_evaluations += 1
    # Require strictly lower immediate risk or, when tied, a strictly better
    # worst-case runway.  Later tie fields only choose among improving moves.
    changed = best[-1] != proposed_action
    lower_risk = best[0] + 1e-9 < proposed[0]
    equal_risk = abs(best[0] - proposed[0]) <= 1e-9
    better_minimum_runway = best[1] < proposed[1]
    if self.viability_shield_runway_only:
      if changed and equal_risk and better_minimum_runway:
        self._viability_suggestion_reason = "runway"
        return best[-1]
    elif changed and best[:3] < proposed[:3]:
      self._viability_suggestion_reason = (
          "immediate_risk" if lower_risk else "runway")
      return best[-1]
    return None

  def stationary_lethal_arrow_escape_action(
      self, obs: SymbolicObservation, proposed_action: str,
  ) -> str | None:
    """Escape a certified fatal stationary arrow update at health one or two.

    This is deliberately narrower than the empirical health-two risk veto.
    It fires only when the proposed action provably leaves the player in an
    arrow's exact next cell, and admits only visible moves outside all such
    cells and beyond every visible zombie's one-move attack reach.
    """
    if (
        not self.stationary_lethal_arrow_escape or
        obs.inventory.get("health", 0) not in {1, 2} or
        self.position not in self.arrow_collision_cells()
    ):
      return None
    direction = ACTION_DIRECTIONS.get(proposed_action)
    if direction is not None:
      proposed_target = add(self.position, direction)
      genuine_move = (
          self.materials.get(proposed_target) in WALKABLE and
          proposed_target not in self.visible_objects)
      if genuine_move:
        return None

    arrows = self.arrow_collision_cells()
    zombies = [
        position for position, name in self.visible_objects.items()
        if name == "zombie"]
    candidates = []
    for action, target in self.legal_safe_moves(obs):
      if target == self.position or target in arrows:
        continue
      if any(manhattan(target, zombie) <= 2 for zombie in zombies):
        continue
      separation = min(
          (manhattan(target, zombie) for zombie in zombies), default=20)
      candidates.append((self.visited[target], -separation, action))
    return min(candidates)[-1] if candidates else None

  def tactical_action(self, obs: SymbolicObservation) -> str | None:
    arrows = self.arrow_collision_cells()
    adjacent = [
        (position, name) for position, name in self.visible_objects.items()
        if name in HOSTILES and manhattan(position, self.position) == 1
    ]

    if self.position in arrows:
      candidates = []
      hostiles = [position for position, name in self.visible_objects.items()
                  if name in HOSTILES]
      for action, target in self.legal_safe_moves(obs):
        if target in arrows:
          continue
        separation = min((manhattan(target, h) for h in hostiles), default=20)
        candidates.append((separation, -self.visited[target], action))
      if candidates:
        return max(candidates)[2]

    nearby_cluster = [
        position for position, name in self.visible_objects.items()
        if name == "zombie" and manhattan(position, self.position) <= 3]
    if self.cluster_escape_direction is not None:
      direction = self.cluster_escape_direction
      target = add(self.position, direction)
      still_pressed = any(
          name == "zombie" and manhattan(position, self.position) <= 4
          for position, name in self.visible_objects.items())
      if (
          self.cluster_escape_steps > 0 and still_pressed and
          self.materials.get(target) in WALKABLE and
          target not in self.visible_objects and target not in arrows
      ):
        self.cluster_escape_steps -= 1
        return DIRECTIONS[direction]
      self.cluster_escape_direction = None
      self.cluster_escape_steps = 0

    if (
        self.cluster_escape_health > 0 and
        obs.inventory.get("health", 0) <= self.cluster_escape_health and
        len(nearby_cluster) >= 2
    ):
      # One-step max-distance rules can reverse direction under a symmetric
      # pack and let equal-speed zombies pin the player.  Pick a locally clear
      # ray once, then retain it for several actions.  The runway term prefers
      # a direction that will not immediately hit a wall; adjacency and local
      # pressure remain hard priorities.
      candidates = []
      for direction, action in DIRECTIONS.items():
        target = add(self.position, direction)
        if (
            self.materials.get(target) not in WALKABLE or
            target in self.visible_objects or target in arrows
        ):
          continue
        distances = [manhattan(target, enemy) for enemy in nearby_cluster]
        runway = 0
        cursor = target
        for _ in range(6):
          if (
              self.materials.get(cursor) not in WALKABLE or
              cursor in self.visible_objects
          ):
            break
          runway += 1
          cursor = add(cursor, direction)
        forward = sum(
            (enemy[0] - target[0]) * direction[0] +
            (enemy[1] - target[1]) * direction[1] > 0
            for enemy in nearby_cluster)
        candidates.append((
            -sum(distance <= 1 for distance in distances),
            -sum(distance <= 2 for distance in distances),
            -forward, runway, min(distances), sum(distances),
            -self.visited[target], action, direction))
      if candidates:
        best = max(candidates)
        self.cluster_escape_direction = best[-1]
        self.cluster_escape_steps = 5
        return best[-2]

    if adjacent:
      has_sword = any(obs.inventory.get(name, 0) for name in (
          "wood_sword", "stone_sword", "iron_sword"))
      nearby_zombies = [
          position for position, name in self.visible_objects.items()
          if name == "zombie" and manhattan(position, self.position) <= 4]
      adjacent_zombies = [
          position for position, name in adjacent if name == "zombie"]
      if (
          self.cooldown_certified_cluster_counterattack and
          obs.inventory.get("stone_sword", 0) and
          2 <= obs.inventory.get("health", 0) <= 6 and
          len(adjacent_zombies) == 2 and len(nearby_zombies) == 2 and
          not any(name in {"skeleton", "arrow"}
                  for name in self.visible_objects.values()) and
          (
              obs.inventory.get("health", 0) >= 5 or
              any((self.zombie_cooldowns.get(position) or 0) > 0
                  for position in adjacent_zombies)
          )
      ):
        # Fleeing from an equal-speed pair can oscillate forever.  With five
        # or more health, at most two fresh two-damage hits are survivable; if
        # health is lower, require a positively inferred cooldown on at least
        # one member.  Once either attacks, its five adjacent-update cooldown
        # spans the two stone-sword strikes needed to kill it.  Restrict this
        # commitment to exactly two visible nearby zombies and no projectile
        # or skeleton ambiguity, then preserve attack tempo by hitting the
        # already-faced member when possible.
        facing_target = add(self.position, self.facing)
        target = min(
            adjacent_zombies,
            key=lambda position: (
                position != facing_target,
                (5 - self.enemy_damage.get(position, ("zombie", 0))[1] + 2) // 3,
                -(self.zombie_cooldowns.get(position) or 0),
                position,
            ),
        )
        direction = sub(target, self.position)
        return "do" if self.facing == direction else DIRECTIONS[direction]
      if (
          self.cooldown_aware_critical_retreat and
          obs.inventory.get("health", 0) <= 2 and adjacent_zombies and
          any(not self.zombie_cooldowns.get(position)
              for position in adjacent_zombies)
      ):
        # Retreat only from a zombie that may attack on this update. A known
        # positive cooldown is precisely the safe two-strike window that the
        # earlier blanket critical-retreat rule threw away.
        candidates = []
        for action, candidate in self.legal_safe_moves(obs):
          adjacency = sum(
              manhattan(candidate, enemy) <= 1 for enemy in nearby_zombies)
          distances = [manhattan(candidate, enemy) for enemy in nearby_zombies]
          candidates.append((
              -adjacency, min(distances, default=20), sum(distances),
              action != "noop", -self.visited[candidate], action))
        if candidates and -max(candidates)[0] < len(adjacent_zombies):
          return max(candidates)[-1]
      if (
          self.critical_single_retreat and
          obs.inventory.get("health", 0) <= 2 and adjacent_zombies
      ):
        # Without a confidently inferred cooldown, even killing the zombie is
        # lethal: Crafter lets a zero-health zombie finish its current update.
        # Take any locally legal move that clears adjacency first.
        hostiles = [
            position for position, name in self.visible_objects.items()
            if name in HOSTILES]
        candidates = []
        for action, candidate in self.legal_safe_moves(obs):
          zombie_adjacency = sum(
              manhattan(candidate, enemy) <= 1 for enemy in nearby_zombies)
          distances = [manhattan(candidate, enemy) for enemy in hostiles]
          candidates.append((
              -zombie_adjacency, min(distances, default=20),
              sum(distances), action != "noop", -self.visited[candidate], action))
        if candidates and -max(candidates)[0] < len(adjacent_zombies):
          return max(candidates)[-1]
      if (
          self.critical_cluster_retreat and
          obs.inventory.get("health", 0) <= 4 and len(nearby_zombies) >= 2
      ):
        # A sword makes one duel short, but it does not prevent the first
        # two-damage hit and a killed zombie still completes its final update.
        # At four health, committing to either member of a cluster is therefore
        # unsafe. Preserve an escape direction until the local pack falls back.
        candidates = []
        for action, candidate in self.legal_safe_moves(obs):
          distances = [manhattan(candidate, enemy) for enemy in nearby_zombies]
          adjacent_after = sum(distance <= 1 for distance in distances)
          close_after = sum(distance <= 2 for distance in distances)
          pressure = sum(max(0, 5 - distance) for distance in distances)
          candidates.append((
              -adjacent_after, -close_after, min(distances), -pressure,
              sum(distances), action != "noop", -self.visited[candidate], action))
        if candidates:
          best = max(candidates)
          current_adjacent = sum(
              manhattan(self.position, enemy) <= 1 for enemy in nearby_zombies)
          if -best[0] < current_adjacent:
            return best[-1]
      if (
          self.low_health_kite and not has_sword and
          obs.inventory.get("health", 0) <= 4
      ):
        hostiles = [
            position for position, name in self.visible_objects.items()
            if name in HOSTILES]
        candidates = []
        for action, candidate in self.legal_safe_moves(obs):
          distances = [manhattan(candidate, enemy) for enemy in hostiles]
          candidates.append((
              min(distances), sum(distances), action != "noop",
              -self.visited[candidate], action))
        if candidates and max(candidates)[0] > 1:
          return max(candidates)[-1]
      # Multiple adjacent enemies can focus damage. Escape if a move strictly
      # reduces adjacency; otherwise commit to killing one rather than oscillate.
      if len(adjacent) >= 2 and obs.inventory.get("health", 0) <= 6:
        candidates = []
        for action, target in self.legal_safe_moves(obs):
          count = sum(manhattan(target, enemy) <= 1 for enemy, _ in adjacent)
          separation = sum(manhattan(target, enemy) for enemy, _ in adjacent)
          candidates.append((-count, separation, action))
        if candidates and max(candidates)[0] > -len(adjacent):
          return max(candidates)[2]
      if self.focus_damaged_enemy:
        target, _ = min(
            adjacent,
            key=lambda item: (
                (5 if item[1] == "zombie" else 3) -
                self.enemy_damage.get(item[0], (item[1], 0))[1],
                item[1] != "zombie", item[0]),
        )
      else:
        facing_target = add(self.position, self.facing)
        facing_enemy = [item for item in adjacent if item[0] == facing_target]
        if self.strike_facing_in_cluster and len(adjacent) >= 2 and facing_enemy:
          # A turn consumes a full hostile update. If an already-faced member
          # of a cluster can be hit now, preserve that attack tempo.
          target, _ = facing_enemy[0]
        else:
          target, _ = min(adjacent, key=lambda item: (item[1] != "zombie", item[0]))
      direction = sub(target, self.position)
      return "do" if self.facing == direction else DIRECTIONS[direction]

    if (
        self.zombie_barrier_health > 0 and
        obs.inventory.get("health", 0) <= self.zombie_barrier_health and
        obs.inventory.get("stone", 0) >= 1 and
        obs.inventory.get("stone_sword", 0)
    ):
      # A faced, axis-aligned zombie at range two is the one geometry where a
      # single ordinary action can prevent its high-probability closing hit:
      # place a solid cell in the empty square between us.  Turning to build
      # would itself expose us to the close, so this is deliberately restricted
      # to the already-faced case.  The generic escape rule handles the next
      # update, and the wall remains useful as cover/choke terrain.
      target = add(self.position, self.facing)
      beyond = add(target, self.facing)
      if (
          self.visible_objects.get(beyond) == "zombie" and
          self.materials.get(target) in PLACEABLE and
          target not in self.visible_objects
      ):
        return "place_stone"

    if (
        self.clear_shelter_pursuer and self.shelter is not None and
        self.shelter.stage in {"route", "route_reuse"} and
        obs.inventory.get("stone_sword", 0) and
        obs.inventory.get("health", 0) >= 3 and
        obs.inventory.get("food", 0) >= 2 and obs.inventory.get("drink", 0) >= 2 and
        not any(name in {"skeleton", "arrow"}
                for name in self.visible_objects.values())
    ):
      zombies = [
          position for position, name in self.visible_objects.items()
          if name == "zombie"]
      if len(zombies) == 1 and manhattan(zombies[0], self.position) == 2:
        # A lone range-two pursuer will normally catch the player during the
        # first stationary mining action of a shelter macro, and can then be
        # joined by later spawns in the open entrance.  Resolve that bounded
        # duel while still on open, remembered terrain.  Unlike universal
        # proactive engagement, this is gated on an already-committed retreat.
        enemy = zombies[0]
        approaches = []
        for direction, action in DIRECTIONS.items():
          target = add(self.position, direction)
          if (
              self.materials.get(target) in WALKABLE and
              target not in self.visible_objects and target not in arrows and
              manhattan(target, enemy) == 1
          ):
            approaches.append((self.visited[target], action))
        if approaches:
          return min(approaches)[1]

    if (
        self.engage_lone_zombie_health > 0 and
        obs.inventory.get("health", 0) >= self.engage_lone_zombie_health and
        obs.inventory.get("stone_sword", 0) and
        (
            not self.engage_lone_zombie_needs_gate or
            (
                obs.inventory.get("drink", 0) > 4 and
                obs.inventory.get("energy", 0) > 2 and
                not (
                    obs.inventory.get("food", 0) <= self.food_hunt_level and
                    any(name == "cow" for name in self.visible_objects.values())
                ) and
                not (
                    not obs.inventory.get("iron_pickaxe", 0) and
                    obs.inventory.get("wood", 0) >= 1 and
                    obs.inventory.get("coal", 0) >= 1 and
                    obs.inventory.get("iron", 0) >= 1 and
                    self.table is not None and self.furnace is not None
                )
            )
        )
    ):
      zombies = [
          position for position, name in self.visible_objects.items()
          if name == "zombie"]
      if len(zombies) == 1 and manhattan(zombies[0], self.position) == 2:
        # Clear an isolated pursuer while health is ample instead of allowing
        # multiple zombies to accumulate around a later stationary mine/craft
        # action.  A stone-sword duel takes two strikes; initiating at range
        # two makes the health cost explicit and bounded in the lone case.
        enemy = zombies[0]
        approaches = []
        for direction, action in DIRECTIONS.items():
          target = add(self.position, direction)
          if (
              self.materials.get(target) in WALKABLE and
              target not in self.visible_objects and target not in arrows and
              manhattan(target, enemy) == 1
          ):
            approaches.append((self.visited[target], action))
        if approaches:
          return min(approaches)[1]

    # A zombie at distance two can move adjacent and attack after this action.
    all_zombies = [position for position, name in self.visible_objects.items()
                   if name == "zombie"]
    close_zombies = [position for position in all_zombies
                     if manhattan(position, self.position) == 2]
    if (close_zombies and
        (self.avoid_single_zombie or len(close_zombies) >= 2 or
         (self.avoid_zombie_clusters and len(all_zombies) >= 2) or
         (self.critical_cluster_retreat and
          obs.inventory.get("health", 0) <= 4 and len(all_zombies) >= 2) or
         obs.inventory.get("health", 0) <= 4)):
      scored_zombies = (
          all_zombies if self.avoid_zombie_clusters and len(all_zombies) >= 2
          else close_zombies)
      candidates = []
      for action, target in self.legal_safe_moves(obs):
        distances = [manhattan(target, z) for z in scored_zombies]
        threatened = sum(distance <= 2 for distance in distances)
        escape_margin = 0
        threat_alignment = 0
        if self.avoid_zombie_clusters and len(scored_zombies) >= 2:
          offsets = [sub(zombie, target) for zombie in scored_zombies]
          threat_alignment = (
              abs(sum(offset[0] for offset in offsets)) +
              abs(sum(offset[1] for offset in offsets)))
          continuations = [target]
          for direction in DIRECTIONS:
            future = add(target, direction)
            if self.materials.get(future) in WALKABLE:
              continuations.append(future)
          escape_margin = max(
              min(manhattan(future, z) for z in scored_zombies)
              for future in continuations)
        candidates.append((
            -threatened, min(distances), threat_alignment, escape_margin,
            sum(distances),
            -self.visited[target], action))
      if candidates:
        best = max(candidates)
        if -best[0] < len(scored_zombies) or best[1] > 2:
          return best[-1]
    return None

  def adjacent_combat_action(self) -> str | None:
    """Stand and focus fire without invalidating an in-progress shelter plan.

    During tunnel construction, moving away can desynchronize the positional
    shelter state machine. Turning toward or striking an adjacent enemy is
    safe: the stage remains valid and a lone zombie dies within its cooldown.
    """
    adjacent = [
        (position, name) for position, name in self.visible_objects.items()
        if name in HOSTILES and manhattan(position, self.position) == 1
    ]
    if not adjacent:
      return None
    target, _ = min(adjacent, key=lambda item: (item[1] != "zombie", item[0]))
    direction = sub(target, self.position)
    return "do" if self.facing == direction else DIRECTIONS[direction]

  def shelter_remaining_actions(self) -> int:
    """Conservative nominal actions until a protected chamber is sealed."""
    if self.shelter is None:
      return 10**6
    remaining = {
        "mine_first": 8,
        "enter_first": 7,
        "mine_second": 6,
        "enter_second": 5,
        "mine_third": 4,
        "enter_third": 3,
        "return_second": 2,
        "seal": 1,
        "enter_reuse_first": 5,
        "enter_reuse_second": 4,
        "enter_reuse_third": 3,
        "return_reuse_second": 2,
        "seal_resupply_enter_third": 5,
        "seal_resupply_mine": 4,
        "seal_resupply_return_second": 2,
    }
    return remaining.get(self.shelter.stage, 0)

  # ---------- High-level policy ----------

  def survival_action(self, obs: SymbolicObservation) -> tuple[str, str] | None:
    inv = obs.inventory
    light = daylight(self.step)
    falling = daylight(self.step + 1) < light

    can_finish_known_diamond = (
        inv.get("iron_pickaxe", 0) > 0 and
        any(material == "diamond" for material in self.materials.values()))
    shelter_light = self.shelter_light
    if inv.get("health", 0) <= 5:
      shelter_light = max(shelter_light, self.low_health_shelter_light)
    if inv.get("iron_pickaxe", 0):
      shelter_light = max(shelter_light, self.post_iron_shelter_light)
    urgent_night = (
        falling and light <= shelter_light and
        not can_finish_known_diamond)
    already_sheltering = self.shelter is not None and self.shelter.stage not in {"idle"}

    if (
        self.emergency_shelter_health > 0 and
        not already_sheltering and self.shelter is not None and
        self.shelter.built and self.shelter.stage == "idle" and
        inv.get("health", 0) <= self.emergency_shelter_health and
        inv.get("food", 0) >= 5 and inv.get("drink", 0) >= 6 and
        sum(
            name == "zombie" and manhattan(position, self.position) <= 4
            for position, name in self.visible_objects.items()) >= 2
    ):
      distance, _ = self.dijkstra(inv)
      if distance.get(self.shelter.stand, 10**12) <= 6:
        self.emergency_sheltering = True
        action = self.shelter_action(obs)
        if action:
          return "emergency_shelter_retreat", action

    if (
        self.deadline_aware_shelter and not already_sheltering and
        falling and light <= 0.75 and self.tool_level(inv) >= 1 and
        not can_finish_known_diamond
    ):
      # The fixed light threshold is adequate only for a shelter beside the
      # player. Schedule the retreat so its route plus exact construction/reuse
      # macro is expected to finish near light 0.30, matching the seal time of
      # a zero-route build started by the accepted light-0.40 policy.
      seal_deadline = next(
          (delta for delta in range(91)
           if daylight(self.step + delta + 1) < daylight(self.step + delta) and
           daylight(self.step + delta) <= 0.30),
          91,
      )
      distance, _ = self.dijkstra(inv)
      candidate = self.choose_shelter(obs)
      predicted = 10**6
      if self.shelter is not None:
        predicted = distance.get(self.shelter.stand, 10**6) + 5
      if candidate is not None:
        candidate_time = distance.get(candidate.stand, 10**6) + 8
        predicted = min(predicted, candidate_time)
      if predicted >= seal_deadline:
        if self.shelter is None and candidate is not None:
          self.shelter = candidate
          self.shelter_sites += 1
        action = self.shelter_action(obs)
        if action:
          return action

    if self.finish_known_diamond and can_finish_known_diamond:
      diamonds = [
          position for position, material in self.materials.items()
          if material == "diamond"]
      distance, _ = self.dijkstra(inv)
      route_costs = [distance[target] for target in diamonds if target in distance]
      if route_costs:
        cost = min(route_costs)
        necessity_budget = min(
            inv.get("food", 0) * 20,
            inv.get("drink", 0) * 16,
            inv.get("energy", 0) * 25,
        )
        if cost + 4 <= necessity_budget:
          return None

    if (
        self.prebuild_shelter and self.shelter is None and self.step < 130 and
        light >= 0.80 and self.tool_level(inv) >= 1
    ):
      # Only take an opportunistic site that is already beside the route and
      # pays back most of its excavation through required stone collection.
      candidate = self.choose_shelter(obs, max_cost=3, min_stone_gain=2)
      if candidate is not None:
        self.shelter = candidate
        self.shelter_sites += 1
        self.preparing_shelter = True
        action = self.shelter_action(obs)
        if action:
          return action
        self.preparing_shelter = False

    # Once the retreat/build has started, do not let ordinary food or water
    # thresholds pull the agent back and forth across the same route. Likewise,
    # enter before soft servicing when current reserves can span the protected
    # interval. Critical reserves still get the chance to service below.
    if self.tool_level(inv) >= 1 and (
        already_sheltering or
        (urgent_night and inv.get("food", 0) >= 3 and inv.get("drink", 0) >= 4)
    ):
      action = self.shelter_action(obs)
      if action:
        return action

    if self.refilling:
      if inv.get("drink", 0) >= 9:
        self.refilling = False
      else:
        action = self.water_action(obs)
        if action:
          return "refill_water", action
        self.refilling = False

    drink_steps = self.awake_drink_steps(inv)
    if self.water_route_margin:
      water_cost = self.water_route_cost(obs)
      wants_known_water = (
          water_cost is not None and
          drink_steps <= water_cost + self.water_route_margin)
    else:
      wants_known_water = (
          drink_steps <= self.drink_buffer_steps
          if self.drink_buffer_steps else
          inv.get("drink", 0) <= self.drink_seek_level)
    if wants_known_water:
      action = self.water_action(obs)
      if action:
        self.refilling = True
        return "seek_water", action

    food_hunt_level = self.food_hunt_level
    if self.adaptive_food and self.step >= 500:
      food_hunt_level = max(food_hunt_level, 6)
    food_steps = self.awake_food_steps(inv)
    wants_visible_food = (
        food_steps <= self.food_buffer_steps
        if self.food_buffer_steps else inv.get("food", 0) <= food_hunt_level)
    if wants_visible_food:
      max_cow_cost = None
      if self.soft_food_hunt_cost and inv.get("food", 0) > 5:
        max_cow_cost = self.soft_food_hunt_cost
      action = self.cow_action(obs, max_cow_cost)
      if action:
        return "hunt_cow", action
      recent_cow_cost = self.recent_cow_cost
      if inv.get("iron_pickaxe", 0) and self.post_iron_recent_cow_cost:
        recent_cow_cost = self.post_iron_recent_cow_cost
      if recent_cow_cost:
        action = self.recent_cow_action(obs, recent_cow_cost)
        if action:
          return "reacquire_cow", action

    if self.food_search_buffer_steps and food_steps <= self.food_search_buffer_steps:
      return "buffer_search_food", self.forage_action(obs)
    if (
        inv.get("iron_pickaxe", 0) and
        self.post_iron_food_search_buffer_steps and
        food_steps <= self.post_iron_food_search_buffer_steps and
        (
            not self.post_iron_food_search_after_steps or
            (
                self.first_iron_pickaxe is not None and
                self.step - self.first_iron_pickaxe >=
                self.post_iron_food_search_after_steps
            )
        ) and
        (
            not self.post_iron_food_search_safe_only or
            not any(
                name in HOSTILES | {"arrow"}
                for name in self.visible_objects.values())
        )
    ):
      return "post_iron_buffer_search_food", self.forage_action(obs)

    urgent_rest = inv.get("energy", 0) <= 2
    if (urgent_night or urgent_rest or already_sheltering) and self.tool_level(inv) >= 1:
      action = self.shelter_action(obs)
      if action:
        return action

    if inv.get("energy", 0) <= 2 and light >= 0.72:
      visible_danger = any(
          name in HOSTILES | {"arrow"} for name in self.visible_objects.values())
      if not visible_danger and inv.get("food", 0) >= 3 and inv.get("drink", 0) >= 3:
        return "open_day_sleep", "sleep"

    if inv.get("drink", 0) <= 2:
      return "search_water", self.frontier_action(obs, prefer_grass=True)
    if inv.get("food", 0) <= 2:
      return "search_food", self.forage_action(obs)
    return None

  def task_action(self, obs: SymbolicObservation) -> tuple[str, str]:
    inv = obs.inventory
    known_diamond = any(material == "diamond" for material in self.materials.values())
    if self.conditional_both_health and self.conditional_both_choice is None:
      if inv.get("health", 0) <= self.conditional_both_health:
        self.conditional_both_choice = True
      elif self.table is not None or inv.get("wood", 0) >= 6:
        # Freeze the safe-world branch before placing the first table so later
        # incidental damage cannot invalidate the precomputed resource bill.
        self.conditional_both_choice = False
    want_early_wood_sword = (
        (self.craft_wood_sword or self.conditional_both_choice is True) and not (
            self.skip_sword_known_diamond and known_diamond))
    adaptive_stone_sword = (
        self.adaptive_sword_cost > 0 and self.adaptive_sword_choice == "stone")

    def after_night_weapon() -> tuple[str, str] | None:
      if (
          not self.after_first_night_wood_sword or not self.has_woken or
          inv.get("wood_sword", 0) or self.table is None
      ):
        return None
      if inv.get("wood", 0) < 1:
        action = self.resource_action(obs, "tree")
        return "after_night_weapon_wood", (
            action or self.frontier_action(obs, prefer_grass=True))
      if self.near_utility(self.table):
        return "make_after_night_wood_sword", "make_wood_sword"
      action = self.route_to_cell(obs, self.table)
      return ("return_for_after_night_wood_sword", action) if action else None

    # Tool ownership, not continued possession of the consumed inputs or
    # continued survival of the workstation, is the technology state. Once an
    # iron pickaxe exists, rebuilding an arrow-destroyed table/furnace or
    # re-collecting coal and iron is pure delay.
    if inv.get("iron_pickaxe", 0):
      if known_diamond:
        action = self.resource_action(obs, "diamond")
        return "collect_diamond", action or self.frontier_action(obs, prefer_mountain=True)
      weapon = after_night_weapon()
      if weapon:
        return weapon
      if (
          self.post_iron_wood_sword and not known_diamond and
          not inv.get("wood_sword", 0) and self.table is not None
      ):
        if inv.get("wood", 0) < 1:
          action = self.resource_action(obs, "tree")
          return "post_iron_weapon_wood", (
              action or self.frontier_action(obs, prefer_grass=True))
        if self.near_utility(self.table):
          return "make_post_iron_wood_sword", "make_wood_sword"
        action = self.route_to_cell(obs, self.table)
        if action:
          return "return_for_post_iron_wood_sword", action
      action = self.resource_action(obs, "diamond")
      return "collect_diamond", action or self.frontier_action(obs, prefer_mountain=True)

    if self.table is None:
      if self.craft_iron_sword and self.craft_stone_sword:
        # Mandatory tool bill (5), stone sword (1), and iron sword (1).
        wood_target = 7
      elif self.craft_stone_sword and want_early_wood_sword:
        # Two distinct swords plus the three pickaxes consume five wood after
        # the two-wood table.
        wood_target = 7
      else:
        wood_target = 6 if (
            self.craft_stone_sword or want_early_wood_sword or
            self.adaptive_sword_cost or
            (self.reactive_wood_sword and self.close_zombie_encountered)
        ) else 5
      if (
          self.craft_stone_sword and inv.get("wood", 0) >= wood_target - 1 and
          self.last_wood_decision_features is None
      ):
        decision_distance, _ = self.dijkstra(inv)
        tree_costs = [
            decision_distance[position]
            for position, material in self.materials.items()
            if material == "tree" and position in decision_distance]
        mountain_l1 = [
            manhattan(self.position, position)
            for position, material in self.materials.items()
            if material in MOUNTAIN]
        self.last_wood_decision_features = {
            "step": self.step,
            "nearest_tree_cost": min(tree_costs) if tree_costs else None,
            "known_trees": len(tree_costs),
            "known_mountain": bool(mountain_l1),
            "nearest_mountain_l1": min(mountain_l1) if mountain_l1 else None,
            "known_water": any(
                material == "water" for material in self.materials.values()),
            "health": inv.get("health", 0),
            "food": inv.get("food", 0),
            "drink": inv.get("drink", 0),
            "energy": inv.get("energy", 0),
        }
      if (
          (self.defer_last_wood_if_cost_gt > 0 or
           self.defer_last_wood_if_cost_le > 0) and
          self.craft_stone_sword and
          inv.get("wood", 0) >= wood_target - 1 and
          self.defer_last_wood_choice is None
      ):
        trees = [
            position for position, material in self.materials.items()
            if material == "tree"]
        distance, _ = self.dijkstra(inv)
        costs = [distance[position] for position in trees if position in distance]
        if self.defer_last_wood_if_cost_le > 0:
          # Defer only when the last tree is cheap now: the early table gains
          # tempo while the remembered pickup remains a bounded later task.
          # If it is expensive, collect it during the initial grassland pass
          # instead of forcing a post-furnace return from the mountain.
          self.defer_last_wood_choice = bool(
              costs and min(costs) <= self.defer_last_wood_if_cost_le)
        else:
          self.defer_last_wood_choice = (
              not costs or min(costs) > self.defer_last_wood_if_cost_gt)
      deferring_last_wood = self.defer_last_wood or (
          self.defer_last_wood_choice is True)
      if deferring_last_wood and self.craft_stone_sword:
        wood_target -= 1
      if inv.get("wood", 0) < wood_target:
        action = self.resource_action(obs, "tree")
        return "collect_wood", action or self.frontier_action(obs, prefer_grass=True)
      if self.cheap_wood_sword_cost and inv.get("wood", 0) == 5:
        trees = [
            position for position, material in self.materials.items()
            if material == "tree"]
        distance, parent = self.dijkstra(inv)
        choices = [(distance[tree], tree) for tree in trees if tree in distance]
        if choices and min(choices)[0] <= self.cheap_wood_sword_cost:
          _, target = min(choices)
          route = self.reconstruct(parent, self.position, target)
          action = self.follow(route, obs)
          if action:
            return "collect_cheap_sword_wood", action
      if (
          not any(material in MOUNTAIN for material in self.materials.values()) and
          not (self.forge_search_deadline and self.step >= self.forge_search_deadline)
      ):
        return "find_mountain_for_forge", self.frontier_action(obs)
      action = self.forge_action(obs)
      if action:
        return action
      return "find_forge_site", self.frontier_action(obs)

    if not inv.get("wood_pickaxe", 0):
      target = self.forge.craft if self.forge else None
      if self.near_utility(self.table):
        return "make_wood_pickaxe", "make_wood_pickaxe"
      action = self.route_to_cell(obs, target) if target else None
      return "return_for_wood_pickaxe", action or self.frontier_action(obs)

    if (
        self.cheap_wood_sword_cost and not inv.get("wood_sword", 0) and
        inv.get("wood", 0) >= 3 and self.near_utility(self.table)
    ):
      return "make_cheap_wood_sword", "make_wood_sword"

    if (
        self.reactive_wood_sword and self.close_zombie_encountered and
        not inv.get("wood_sword", 0) and inv.get("wood", 0) >= 3 and
        self.near_utility(self.table)
    ):
      return "make_reactive_wood_sword", "make_wood_sword"

    if want_early_wood_sword and not inv.get("wood_sword", 0):
      if self.near_utility(self.table):
        return "make_wood_sword", "make_wood_sword"
      target = self.forge.craft if self.forge else self.table
      action = self.route_to_cell(obs, target) if target else None
      return "return_for_wood_sword", action or self.frontier_action(obs)

    weapon = after_night_weapon()
    if weapon:
      return weapon

    # Delay the weapon choice until five stones have been collected.  At that
    # point the local map can answer whether the sixth stone needed for a stone
    # sword is genuinely cheap.  This retains the lower preparation bill on
    # sparse geometries without trying to predict stone availability at spawn.
    if (
        self.adaptive_sword_cost and self.adaptive_sword_choice is None and
        inv.get("stone", 0) >= 5
    ):
      stones = [
          position for position, material in self.materials.items()
          if material == "stone"]
      distance, _ = self.dijkstra(inv)
      costs = [distance[position] for position in stones if position in distance]
      self.adaptive_sword_choice = (
          "stone" if costs and min(costs) <= self.adaptive_sword_cost else "wood")

    if (
        self.adaptive_sword_choice == "wood" and
        not inv.get("wood_sword", 0)
    ):
      if self.near_utility(self.table):
        return "make_adaptive_wood_sword", "make_wood_sword"
      action = self.route_to_cell(obs, self.forge.craft if self.forge else self.table)
      return "return_for_adaptive_wood_sword", action or self.frontier_action(obs)

    if not inv.get("stone_pickaxe", 0):
      stone_target = 6 if (self.craft_stone_sword or adaptive_stone_sword) else 5
      if inv.get("stone", 0) < stone_target:
        action = self.resource_action(obs, "stone")
        return "collect_stone", action or self.frontier_action(obs, prefer_mountain=True)
      if (
          self.mobile_workstation_savings > 0 and self.table is not None and
          self.furnace is None and inv.get("wood", 0) >= 4
      ):
        # A table costs two wood, while the pending stone pickaxe and stone
        # sword cost two more.  If all four are already carried, a local
        # satellite forge can dominate a long exposed commute to the first
        # table.  This uses only the remembered local map; it does not know
        # global coordinates or hidden resource locations.
        distance, _ = self.dijkstra(inv)
        old_target = self.forge.craft if self.forge else self.table
        old_cost = distance.get(old_target, 10**12)
        candidate = self.choose_forge(obs)
        new_cost = (
            distance.get(candidate.table_approach, 10**12)
            if candidate is not None else 10**12)
        if old_cost - new_cost >= self.mobile_workstation_savings:
          self.forge = candidate
          self.table = None
          self.workstation_relocations += 1
          placement = self.forge_action(obs)
          if placement:
            _, action = placement
            return "relocate_table", action
      if self.near_utility(self.table):
        return "make_stone_pickaxe", "make_stone_pickaxe"
      target = self.forge.craft if self.forge else self.table
      action = self.route_to_cell(obs, target) if target else None
      return "return_for_stone_pickaxe", action or self.frontier_action(obs, prefer_mountain=True)

    if (self.craft_stone_sword or adaptive_stone_sword) and not inv.get("stone_sword", 0):
      if self.near_utility(self.table):
        return "make_stone_sword", "make_stone_sword"
      target = self.forge.craft if self.forge else self.table
      action = self.route_to_cell(obs, target) if target else None
      return "return_for_stone_sword", action or self.frontier_action(obs, prefer_mountain=True)

    if self.furnace is None:
      if inv.get("stone", 0) < 4 + self.stone_reserve:
        action = self.resource_action(obs, "stone")
        return "collect_furnace_stone", action or self.frontier_action(obs, prefer_mountain=True)
      action = self.forge_action(obs)
      if action:
        return action
      return "recover_furnace_site", self.frontier_action(obs, prefer_mountain=True)

    if (
        (self.defer_last_wood or self.defer_last_wood_choice is True) and
        inv.get("wood", 0) < 1
    ):
      action = self.resource_action(obs, "tree")
      return "collect_deferred_wood", (
          action or self.frontier_action(obs, prefer_grass=True))

    coal_target = 2 if self.craft_iron_sword else 1
    if inv.get("coal", 0) < coal_target:
      action = self.resource_action(obs, "coal")
      return "collect_coal", action or self.frontier_action(obs, prefer_mountain=True)

    iron_target = 2 if self.craft_iron_sword else 1
    if inv.get("iron", 0) < iron_target:
      action = self.resource_action(obs, "iron")
      return "collect_iron", action or self.frontier_action(obs, prefer_mountain=True)

    if not inv.get("iron_pickaxe", 0):
      if (
          self.mobile_workstation_savings > 0 and
          self.table is not None and self.furnace is not None and
          inv.get("wood", 0) >= 3 and inv.get("stone", 0) >= 4
      ):
        # Once coal and iron are carried, rebuilding both utilities needs two
        # wood plus four stone and leaves the third wood for the iron pickaxe.
        # Admit this only when the local placement approach beats the old
        # shared craft cell by the configured conservative margin.
        distance, _ = self.dijkstra(inv)
        old_target = self.forge.craft if self.forge else self.table
        old_cost = distance.get(old_target, 10**12)
        candidate = self.choose_forge(obs)
        new_cost = (
            distance.get(candidate.table_approach, 10**12)
            if candidate is not None else 10**12)
        if old_cost - new_cost >= self.mobile_workstation_savings:
          self.forge = candidate
          self.table = None
          self.furnace = None
          self.workstation_relocations += 1
          placement = self.forge_action(obs)
          if placement:
            _, action = placement
            return "relocate_forge", action
      if self.near_utility(self.table) and self.near_utility(self.furnace):
        if self.craft_iron_sword and not inv.get("iron_sword", 0):
          return "make_iron_sword", "make_iron_sword"
        # Incidental path clearing sometimes leaves wood beyond the exact
        # technology bill. Spend only that surplus, at zero routing cost.
        if (
            self.opportunistic_wood_sword and
            not inv.get("wood_sword", 0) and inv.get("wood", 0) >= 2
        ):
          return "make_opportunistic_wood_sword", "make_wood_sword"
        return "make_iron_pickaxe", "make_iron_pickaxe"
      target = self.forge.craft if self.forge else None
      action = self.route_to_cell(obs, target) if target else None
      return "return_for_iron_pickaxe", action or self.frontier_action(obs, prefer_mountain=True)

    action = self.resource_action(obs, "diamond")
    return "collect_diamond", action or self.frontier_action(obs, prefer_mountain=True)

  def act(self, obs: SymbolicObservation) -> str:
    self.observe(obs)
    protected = False
    if obs.sleeping:
      decision = ("sleeping", "noop")
    else:
      protected_stages = {
          "mine_first", "enter_first", "mine_second", "enter_second",
          "mine_third", "enter_third", "return_second", "seal", "sheltered",
          "unseal", "exit_first", "exit_stand", "enter_reuse_first",
          "enter_reuse_second", "enter_reuse_third", "return_reuse_second",
          "prepare_exit_first", "prepare_exit_stand",
          "night_mine_out", "night_mine_return", "night_mine_reseal",
          "seal_resupply_enter_third", "seal_resupply_mine",
          "seal_resupply_return_second", "compact_seal_resupply_mine",
      }
      protected = self.shelter is not None and self.shelter.stage in protected_stages
      allow_protected_combat = self.shelter_combat or (
          self.shelter_combat_min_remaining > 0 and
          self.shelter_remaining_actions() >= self.shelter_combat_min_remaining)
      protected_combat = (
          self.adjacent_combat_action()
          if protected and allow_protected_combat else None)
      if (
          protected_combat and self.low_health_kite and
          obs.inventory.get("health", 0) <= 4 and
          not any(obs.inventory.get(name, 0) for name in (
              "wood_sword", "stone_sword", "iron_sword"))
      ):
        protected_combat = self.tactical_action(obs)
        if protected_combat in ACTION_DIRECTIONS:
          # A movement dodge invalidates the positional tunnel stage. Restart
          # from its remembered outer stand; already excavated cells are then
          # skipped by the normal shelter state machine.
          self.shelter.stage = "route"
      shelter_decision = self.shelter_action(obs) if protected else None
      if protected_combat:
        decision = ("shelter_combat", protected_combat)
      elif shelter_decision:
        decision = shelter_decision
      else:
        action = self.tactical_action(obs)
        if action:
          decision = ("tactical", action)
        else:
          decision = self.survival_action(obs) or self.task_action(obs)

    self.mode, action = decision
    avoid_arrow = (
        self.avoid_entering_arrow or
        (self.avoid_arrow_health > 0 and
         obs.inventory.get("health", 0) <= self.avoid_arrow_health))
    if avoid_arrow and action in ACTION_DIRECTIONS:
      target = add(self.position, ACTION_DIRECTIONS[action])
      # Movement into a solid/object is only a turn and leaves the player in
      # place.  Override only genuine moves into an arrow's next collision
      # cell; a one-step wait lets the projectile pass without corrupting the
      # high-level task state.
      if (
          self.materials.get(target) in WALKABLE and
          target not in self.visible_objects and
          target in self.arrow_collision_cells()
      ):
        self.mode, action = "avoid_arrow_target", "noop"
    stationary_arrow_escape = self.stationary_lethal_arrow_escape_action(
        obs, action)
    if stationary_arrow_escape is not None:
      if protected and self.shelter is not None:
        self.shelter.stage = "route"
      self.mode, action = (
          "stationary_lethal_arrow_escape", stationary_arrow_escape)
      self.stationary_lethal_arrow_escapes += 1
    critical_escape = self.critical_escape_action(obs, action)
    if critical_escape is not None:
      if (
          protected and critical_escape in ACTION_DIRECTIONS and
          self.shelter is not None
      ):
        # The high-level shelter macro may already have advanced its stage for
        # the proposed action. An unplanned displacement must restart routing
        # from the remembered stand rather than reuse stale positional state.
        self.shelter.stage = "route"
      self.mode, action = "critical_risk_veto", critical_escape
      self.critical_risk_vetoes += 1
    # Sleeping and the positional interior of a shelter are atomic.  The
    # shield may protect the exposed route/exit, but must not dismantle a
    # completed chamber merely because a zombie is visible through the crop.
    viability_escape = (
        None if obs.sleeping or protected else
        self.viability_escape_action(obs, action))
    if viability_escape is not None:
      self.viability_shield_suggestions += 1
      self.viability_shield_suggestion_modes[self.mode] += 1
      reason = self._viability_suggestion_reason or "unknown"
      self.viability_shield_suggestion_reasons[reason] += 1
      self.viability_shield_last_suggestion = {
          "step": self.step,
          "mode": self.mode,
          "proposed": action,
          "suggested": viability_escape,
          "reason": reason,
          "health": obs.inventory.get("health", 0),
      }
      if not self.viability_shield_shadow:
        if (
            protected and viability_escape in ACTION_DIRECTIONS and
            self.shelter is not None
        ):
          self.shelter.stage = "route"
        self.mode, action = "viability_shield", viability_escape
        self.viability_shield_interventions += 1
    self.mode_counts[self.mode] += 1
    self.last_action = action
    self.last_observation = obs
    self.step += 1
    return action
