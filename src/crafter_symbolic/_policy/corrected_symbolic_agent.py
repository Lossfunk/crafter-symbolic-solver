"""RGB-grounded successor to the frozen privileged Crafter champion."""

from __future__ import annotations

from typing import Any

import numpy as np

from .crafter_rgb_decoder import CrafterRGBDecoder
from .config import ACTION_NAMES, FINAL_CONFIG
from .heuristic_agent import (
    ACTION_DIRECTIONS,
    WALKABLE,
    SymbolicObservation,
    add,
)
from .score_agent import CrafterScoreAgent
from .visual_symbolic_observation import VisualSymbolicObservation


POLICY_NAME = "rgb_grounded_v8_score_v2_uncertainty_v1"
UNKNOWN_OBJECT = "__unknown_object__"
LOCAL_OFFSETS = frozenset(
    (x, y) for x in range(-4, 5) for y in range(-3, 4))


class CorrectedAgent(CrafterScoreAgent):
  """Preserve the v1 policy while making negative visual evidence explicit."""

  policy_name = POLICY_NAME

  def __init__(self, *, decoder: CrafterRGBDecoder | None = None) -> None:
    super().__init__(**FINAL_CONFIG)
    self.decoder = decoder or CrafterRGBDecoder()
    self._visual_facing = (0, 1)
    self._last_object_absent: frozenset[tuple[int, int]] = frozenset()
    self._pending_visual: VisualSymbolicObservation | None = None
    self.perception_frames = 0
    self.perception_material_facts = 0
    self.perception_absence_facts = 0
    self.perception_object_facts = 0

  def reset(self) -> None:
    decoder = self.decoder
    self.__init__(decoder=decoder)

  def _commit_previous_action(self) -> None:
    """Advance odometry only from a certified-empty decision-time target."""
    if self.last_action not in ACTION_DIRECTIONS or self.last_observation is None:
      return
    direction = ACTION_DIRECTIONS[self.last_action]
    self.facing = direction
    if self.last_observation.sleeping:
      return
    if direction not in self._last_object_absent:
      return
    target = add(self.position, direction)
    material = self.last_observation.materials.get(direction)
    if material is None:
      material = self.materials.get(target)
    if material in WALKABLE | {"lava"}:
      self.position = target

  def observe(self, obs: SymbolicObservation) -> None:
    """Run legacy belief updates without turning abstention into absence."""
    visual = self._pending_visual
    if visual is None:
      raise RuntimeError("visual observation missing during policy update")
    prior_last_seen = dict(self.last_seen_objects)
    super().observe(obs)

    known_object_offsets = set(visual.objects) | set(visual.object_absent)
    unknown_offsets = LOCAL_OFFSETS - known_object_offsets
    unknown_absolute = {add(self.position, offset) for offset in unknown_offsets}
    for position in unknown_absolute:
      if position in prior_last_seen:
        self.last_seen_objects[position] = prior_last_seen[position]
      else:
        self.last_seen_objects.pop(position, None)

    # In the score extension, this set is used as negative evidence for a
    # remembered cow or plant. Include only cells whose object channel and
    # material channel were both certified for the legacy update.
    self.current_visible_cells = {
        add(self.position, offset)
        for offset in known_object_offsets
        if offset in visual.materials
    }

  def act_visual(self, visual: VisualSymbolicObservation) -> str:
    """Choose an action from an already pixel-grounded symbolic observation."""
    if visual.step != self.step:
      raise ValueError(
          f"observation step {visual.step} does not match agent step {self.step}")

    known_object_offsets = set(visual.objects) | set(visual.object_absent)
    unknown_offsets = LOCAL_OFFSETS - known_object_offsets
    # The legacy score observer uses known material cells as its negative
    # object-evidence set. Supplying a material only when the object channel is
    # also known prevents an uncertain object from being declared absent.
    safe_materials = {
        offset: material
        for offset, material in visual.materials.items()
        if offset in known_object_offsets
    }
    proxy_objects = dict(visual.objects)
    proxy_objects.update({offset: UNKNOWN_OBJECT for offset in unknown_offsets})
    proxy = SymbolicObservation(
        materials=safe_materials,
        objects=proxy_objects,
        object_directions=dict(visual.object_directions),
        inventory=dict(visual.inventory),
        facing=visual.facing,
        sleeping=visual.sleeping,
        reward=visual.reward,
    )

    self._pending_visual = visual
    try:
      action = super().act(proxy)
    finally:
      self._pending_visual = None
    self._last_object_absent = visual.object_absent
    if action not in ACTION_NAMES:
      raise RuntimeError(f"controller emitted unknown action {action!r}")
    return action

  def act(self, frame: np.ndarray, reward: float = 0.0) -> str:
    """Decode the exact returned RGB frame and emit one Crafter action."""
    visual = self.decoder.decode(
        frame,
        step=self.step,
        previous_facing=self._visual_facing,
        reward=reward,
    )
    self.perception_frames += 1
    self.perception_material_facts += len(visual.materials)
    self.perception_absence_facts += len(visual.object_absent)
    self.perception_object_facts += len(visual.objects)
    self._visual_facing = visual.facing
    return self.act_visual(visual)


def make_agent(**kwargs: Any) -> CorrectedAgent:
  return CorrectedAgent(**kwargs)


__all__ = [
    "CorrectedAgent",
    "LOCAL_OFFSETS",
    "POLICY_NAME",
    "UNKNOWN_OBJECT",
    "make_agent",
]
