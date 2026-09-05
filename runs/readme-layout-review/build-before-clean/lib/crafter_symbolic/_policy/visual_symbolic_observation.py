"""Uncertainty-aware observation record for the RGB-grounded agent line."""

from __future__ import annotations

import dataclasses


Offset = tuple[int, int]
Direction = tuple[int, int]


@dataclasses.dataclass(frozen=True)
class VisualSymbolicObservation:
  """Facts decoded from one RGB frame, with negative evidence explicit.

  Missing material and object entries mean unknown. A cell is certified to
  contain no non-player object only when it is present in ``object_absent``.
  The three states (known present, known absent, unknown) are therefore
  distinct.
  """

  materials: dict[Offset, str]
  objects: dict[Offset, str]
  object_absent: frozenset[Offset]
  object_directions: dict[Offset, Direction]
  inventory: dict[str, int]
  facing: Direction
  sleeping: bool
  material_margin: dict[Offset, float] = dataclasses.field(default_factory=dict)
  object_margin: dict[Offset, float] = dataclasses.field(default_factory=dict)
  step: int = 0
  reward: float = 0.0

  def __post_init__(self) -> None:
    overlap = set(self.objects) & set(self.object_absent)
    if overlap:
      raise ValueError(
          f"cells cannot contain an object and certify absence: {overlap!r}")
    valid = {(x, y) for x in range(-4, 5) for y in range(-3, 4)}
    supplied = (
        set(self.materials) | set(self.objects) | set(self.object_absent) |
        set(self.object_directions))
    outside = supplied - valid
    if outside:
      raise ValueError(f"offsets outside the 9-by-7 crop: {outside!r}")
    if set(self.object_directions) - set(self.objects):
      raise ValueError("object directions require a known present object")
    if self.facing not in {(-1, 0), (1, 0), (0, -1), (0, 1)}:
      raise ValueError(f"invalid cardinal facing {self.facing!r}")


__all__ = ["Direction", "Offset", "VisualSymbolicObservation"]
