"""Pixel-only symbolic decoder for the paper-default Crafter observation.

The inference methods accept only an RGB array, an episode step, previous
facing memory, and immutable public textures/mechanics. Simulator world state,
the semantic map, numeric player fields, and RNG state are not inputs.

Daylight decoding is deterministic. Night scores use the public renderer's
noise model, but hard night labels intentionally remain abstained until their
likelihood margins have been calibrated on held-out frames.
"""

from __future__ import annotations

import dataclasses
import importlib.util
import math
import pathlib

import numpy as np
from PIL import Image, ImageEnhance

from .visual_symbolic_observation import VisualSymbolicObservation


TILE = 7
WORLD_COLUMNS = 9
WORLD_ROWS = 7
WORLD_WIDTH = WORLD_COLUMNS * TILE
WORLD_HEIGHT = WORLD_ROWS * TILE
HUD_ROWS = 2
HUD_HEIGHT = HUD_ROWS * TILE
FRAME_SIZE = 64

MATERIALS = (
    "water", "grass", "stone", "path", "sand", "tree", "lava", "coal",
    "iron", "diamond", "table", "furnace", "void",
)
WALKABLE = ("grass", "path", "sand")
ARROW_MATERIALS = WALKABLE + ("water", "lava")
PLAYER_MATERIALS = WALKABLE + ("lava",)
ITEMS = (
    "health", "food", "drink", "energy", "sapling", "wood", "stone",
    "coal", "iron", "diamond", "wood_pickaxe", "stone_pickaxe",
    "iron_pickaxe", "wood_sword", "stone_sword", "iron_sword",
)
CARDINALS = {
    "left": (-1, 0),
    "right": (1, 0),
    "up": (0, -1),
    "down": (0, 1),
}

# Frozen after development calibration on bases 92,000,000 and 93,000,000.
# The separate base-94,000,000 perception court is reserved for validation.
NIGHT_MATERIAL_MARGIN = 0.12
NIGHT_OBJECT_ABSENCE_MARGIN = 1e-9
NIGHT_OBJECT_PRESENCE_MARGIN = 0.02


def daylight(step: int) -> float:
  progress = (step / 300) % 1 + 0.3
  return 1 - abs(math.cos(math.pi * progress)) ** 3


@dataclasses.dataclass(frozen=True)
class CellState:
  material: str
  object_name: str | None = None
  direction: tuple[int, int] | None = None
  player_facing: tuple[int, int] | None = None
  sleeping: bool = False


@dataclasses.dataclass(frozen=True)
class RankedCell:
  state: CellState
  score: float
  material_margin: float
  object_margin: float


def _default_asset_dir() -> pathlib.Path:
  spec = importlib.util.find_spec("crafter")
  if spec is None or not spec.submodule_search_locations:
    raise RuntimeError("Crafter must be installed to locate its public assets")
  return pathlib.Path(next(iter(spec.submodule_search_locations))) / "assets"


def _resize_texture(path: pathlib.Path, size: int) -> np.ndarray:
  with Image.open(path) as image:
    return np.asarray(image.resize((size, size), resample=Image.Resampling.NEAREST))


def _draw_alpha(background: np.ndarray, texture: np.ndarray) -> np.ndarray:
  if texture.shape[-1] != 4:
    return texture[..., :3].astype(np.uint8)
  alpha = texture[..., 3:].astype(np.float32) / 255
  foreground = texture[..., :3].astype(np.float32) / 255
  current = background.astype(np.float32) / 255
  return (255 * (alpha * foreground + (1 - alpha) * current)).astype(np.uint8)


def _tint(canvas: np.ndarray, color: tuple[int, int, int]) -> np.ndarray:
  return 0.5 * canvas + 0.5 * np.asarray(color, dtype=np.float64)


class CrafterRGBDecoder:
  """Decode observations using only public render assets and received pixels."""

  def __init__(self, asset_dir: pathlib.Path | str | None = None) -> None:
    self.asset_dir = pathlib.Path(asset_dir) if asset_dir else _default_asset_dir()
    self._textures: dict[tuple[str, int], np.ndarray] = {}
    self._cell_states, self._cell_clean = self._build_cell_candidates()
    self._player_states, self._player_clean = self._build_player_candidates()
    self._hud_templates = self._build_hud_templates()
    self._vignette = self._build_vignette()
    self._day_cache: dict[tuple[int, bool, bool], np.ndarray] = {}
    self._night_cache_step: tuple[int, bool] | None = None
    self._night_cache: dict[
        tuple[bool, tuple[int, int]], tuple[np.ndarray, np.ndarray]
    ] = {}

  def _texture(self, name: str, size: int) -> np.ndarray:
    key = name, size
    if key not in self._textures:
      path = self.asset_dir / f"{name}.png"
      if not path.exists():
        raise RuntimeError(f"missing Crafter public texture: {path}")
      self._textures[key] = _resize_texture(path, size)
    return self._textures[key]

  def _material_tile(self, material: str) -> np.ndarray:
    if material == "void":
      return np.full((TILE, TILE, 3), 127, np.uint8)
    return self._texture(material, TILE)[..., :3].astype(np.uint8)

  def _composite(self, material: str, texture_name: str) -> np.ndarray:
    return _draw_alpha(
        self._material_tile(material), self._texture(texture_name, TILE))

  def _build_cell_candidates(self) -> tuple[tuple[CellState, ...], np.ndarray]:
    records: list[tuple[CellState, np.ndarray]] = []
    for material in MATERIALS:
      records.append((CellState(material), self._material_tile(material)))
    for material in WALKABLE:
      for object_name in ("cow", "zombie", "skeleton"):
        records.append((
            CellState(material, object_name),
            self._composite(material, object_name),
        ))
    for material in ARROW_MATERIALS:
      for suffix, direction in CARDINALS.items():
        records.append((
            CellState(material, "arrow", direction=direction),
            self._composite(material, f"arrow-{suffix}"),
        ))
    for object_name, texture_name in (
        ("plant", "plant"), ("plant_ripe", "plant-ripe")):
      records.append((
          CellState("grass", object_name),
          self._composite("grass", texture_name),
      ))
    return (
        tuple(state for state, _ in records),
        np.stack([image for _, image in records]),
    )

  def _build_player_candidates(self) -> tuple[tuple[CellState, ...], np.ndarray]:
    records: list[tuple[CellState, np.ndarray]] = []
    for material in PLAYER_MATERIALS:
      for suffix, direction in CARDINALS.items():
        records.append((
            CellState(material, player_facing=direction),
            self._composite(material, f"player-{suffix}"),
        ))
      records.append((
          CellState(material, sleeping=True),
          self._composite(material, "player-sleep"),
      ))
    return (
        tuple(state for state, _ in records),
        np.stack([image for _, image in records]),
    )

  def _build_hud_templates(self) -> dict[str, np.ndarray]:
    templates: dict[str, np.ndarray] = {}
    for item in ITEMS:
      amounts = []
      for amount in range(10):
        cell = np.zeros((TILE, TILE, 3), np.uint8)
        if amount:
          icon = self._texture(item, int(0.8 * TILE))
          cell[:icon.shape[0], :icon.shape[1]] = _draw_alpha(
              cell[:icon.shape[0], :icon.shape[1]], icon)
          digit = self._texture(str(amount), int(0.6 * TILE))
          row = column = int(0.4 * TILE)
          region = cell[row:row + digit.shape[0], column:column + digit.shape[1]]
          cell[row:row + digit.shape[0], column:column + digit.shape[1]] = (
              _draw_alpha(region, digit))
        amounts.append(cell)
      templates[item] = np.stack(amounts)
    return templates

  @staticmethod
  def _build_vignette() -> np.ndarray:
    rows, columns = np.meshgrid(
        np.linspace(-1, 1, WORLD_HEIGHT),
        np.linspace(-1, 1, WORLD_WIDTH),
        indexing="ij",
    )
    return 1 - np.exp(-0.5 * (columns ** 2 + rows ** 2) / (0.5 ** 2))

  @staticmethod
  def _validate_frame(frame: np.ndarray) -> np.ndarray:
    value = np.asarray(frame)
    if value.shape != (FRAME_SIZE, FRAME_SIZE, 3):
      raise ValueError(
          f"expected paper-default RGB shape (64, 64, 3), got {value.shape}")
    if value.dtype != np.uint8:
      if np.any((value < 0) | (value > 255)):
        raise ValueError("RGB values must lie in [0, 255]")
      value = value.astype(np.uint8)
    return value

  def decode_hud(self, frame: np.ndarray) -> dict[str, int]:
    """Decode all sixteen fixed HUD slots by public-template matching."""
    frame = self._validate_frame(frame)
    inventory = {}
    for index, item in enumerate(ITEMS):
      column = index % WORLD_COLUMNS
      row = index // WORLD_COLUMNS
      top = WORLD_HEIGHT + row * TILE
      left = column * TILE
      cell = frame[top:top + TILE, left:left + TILE].astype(np.int16)
      candidates = self._hud_templates[item].astype(np.int16)
      errors = np.sum(np.abs(candidates - cell), axis=(1, 2, 3))
      inventory[item] = int(np.argmin(errors))
    return inventory

  def _render_candidates(
      self,
      clean: np.ndarray,
      *,
      step: int,
      offset: tuple[int, int],
      sleeping: bool,
      noise_value: float | None,
  ) -> np.ndarray:
    light = daylight(step)
    dx, dy = offset
    top = (dy + 3) * TILE
    left = (dx + 4) * TILE
    mask = self._vignette[top:top + TILE, left:left + TILE]
    night = clean.astype(np.float64)
    if light < 0.5:
      if noise_value is None:
        raise ValueError("night rendering requires a noise representative")
      amount = 2 * (0.5 - light)
      mixed = amount * mask
      night = (
          (1 - mixed[None, ..., None]) * night +
          mixed[None, ..., None] * noise_value)
    count = len(clean)
    # PIL's color enhancement is pixel-local. Packing every candidate into one
    # tall image is exactly equivalent to thousands of tiny calls and makes
    # full-episode decoding practical.
    packed = night.astype(np.uint8).reshape(count * TILE, TILE, 3)
    packed = np.asarray(
        ImageEnhance.Color(Image.fromarray(packed)).enhance(0.4))
    night = packed.reshape(count, TILE, TILE, 3)
    night = _tint(night, (0, 16, 64))
    image = light * clean + (1 - light) * night
    if sleeping:
      packed = image.astype(np.uint8).reshape(count * TILE, TILE, 3)
      packed = np.asarray(
          ImageEnhance.Color(Image.fromarray(packed)).enhance(0.0))
      image = packed.reshape(count, TILE, TILE, 3)
      image = _tint(image, (0, 0, 16))
    return image.astype(np.uint8)

  def _candidate_scores(
      self,
      observed: np.ndarray,
      clean: np.ndarray,
      *,
      step: int,
      offset: tuple[int, int],
      sleeping: bool,
      player: bool,
  ) -> np.ndarray:
    """Score candidates against the deterministic or bounded-noise renderer."""
    if daylight(step) >= 0.5:
      key = step % 300, sleeping, player
      rendered = self._day_cache.get(key)
      if rendered is None:
        rendered = self._render_candidates(
            clean, step=step, offset=(0, 0), sleeping=sleeping,
            noise_value=79.5)
        self._day_cache[key] = rendered
      residual = rendered.astype(np.float64) - observed.astype(np.float64)
      return np.sum(residual * residual, axis=(1, 2, 3))

    step_key = step % 300, sleeping
    if self._night_cache_step != step_key:
      self._night_cache_step = step_key
      self._night_cache.clear()
    cache_key = player, offset
    endpoints = self._night_cache.get(cache_key)
    if endpoints is None:
      endpoints = (
          self._render_candidates(
              clean, step=step, offset=offset, sleeping=sleeping,
              noise_value=32),
          self._render_candidates(
              clean, step=step, offset=offset, sleeping=sleeping,
              noise_value=127),
      )
      self._night_cache[cache_key] = endpoints
    low, high = endpoints
    point = observed.astype(np.float64)[None, ...]
    start = low.astype(np.float64)
    vector = high.astype(np.float64) - start
    numerator = np.sum((point - start) * vector, axis=-1)
    denominator = np.sum(vector * vector, axis=-1)
    fraction = np.divide(
        numerator, denominator,
        out=np.zeros_like(numerator), where=denominator > 0)
    fraction = np.clip(fraction, 0, 1)[..., None]
    closest = start + fraction * vector
    residual = point - closest
    return np.sum(residual * residual, axis=(1, 2, 3))

  @staticmethod
  def _group_margin(
      scores: np.ndarray,
      states: tuple[CellState, ...],
      key,
  ) -> float:
    grouped: dict[object, float] = {}
    for score, state in zip(scores, states):
      value = key(state)
      grouped[value] = min(grouped.get(value, float("inf")), float(score))
    ordered = sorted(grouped.values())
    return (ordered[1] - ordered[0]) / (TILE * TILE) if len(ordered) > 1 else float("inf")

  def rank_cell(
      self,
      frame: np.ndarray,
      *,
      step: int,
      offset: tuple[int, int],
      sleeping: bool = False,
      player: bool = False,
  ) -> RankedCell:
    """Return the best public-render candidate and channel margins."""
    frame = self._validate_frame(frame)
    dx, dy = offset
    if dx not in range(-4, 5) or dy not in range(-3, 4):
      raise ValueError(f"offset outside local crop: {offset!r}")
    top = (dy + 3) * TILE
    left = (dx + 4) * TILE
    observed = frame[top:top + TILE, left:left + TILE]
    states = self._player_states if player else self._cell_states
    clean = self._player_clean if player else self._cell_clean
    if player:
      # The player sprite is also the only source of the sleep flag, while the
      # sleep transform is applied to the whole world view after drawing that
      # sprite. Score awake sprites through the awake transform and the sleep
      # sprite through the sleep transform rather than assuming the unknown
      # flag in advance.
      scores = np.full(len(states), float("inf"))
      for candidate_sleeping in (False, True):
        indices = np.asarray([
            index for index, state in enumerate(states)
            if state.sleeping == candidate_sleeping
        ])
        scores[indices] = self._candidate_scores(
            observed,
            clean[indices],
            step=step,
            offset=offset,
            sleeping=candidate_sleeping,
            player=player,
        )
    else:
      scores = self._candidate_scores(
          observed, clean, step=step, offset=offset, sleeping=sleeping,
          player=player)
    index = int(np.argmin(scores))
    return RankedCell(
        state=states[index],
        score=float(scores[index]) / (TILE * TILE),
        material_margin=self._group_margin(
            scores, states, lambda state: state.material),
        object_margin=self._group_margin(
            scores,
            states,
            lambda state: (
                "player" if player else
                (state.object_name, state.direction)),
        ),
    )

  def decode(
      self,
      frame: np.ndarray,
      *,
      step: int,
      previous_facing: tuple[int, int] = (0, 1),
      reward: float = 0.0,
      night_material_margin: float = NIGHT_MATERIAL_MARGIN,
      night_object_absence_margin: float = NIGHT_OBJECT_ABSENCE_MARGIN,
      night_object_presence_margin: float = NIGHT_OBJECT_PRESENCE_MARGIN,
  ) -> VisualSymbolicObservation:
    """Decode one frame, abstaining on uncertified night world channels."""
    frame = self._validate_frame(frame)
    center = self.rank_cell(
        frame, step=step, offset=(0, 0), player=True)
    sleeping = center.state.sleeping
    facing = previous_facing if sleeping else center.state.player_facing
    if facing is None:
      facing = previous_facing

    materials: dict[tuple[int, int], str] = {}
    objects: dict[tuple[int, int], str] = {}
    absent: set[tuple[int, int]] = set()
    directions: dict[tuple[int, int], tuple[int, int]] = {}
    material_margins: dict[tuple[int, int], float] = {}
    object_margins: dict[tuple[int, int], float] = {}
    deterministic = daylight(step) >= 0.5

    for dx in range(-4, 5):
      for dy in range(-3, 4):
        offset = dx, dy
        if offset == (0, 0):
          ranked = center
        else:
          ranked = self.rank_cell(
              frame, step=step, offset=offset, sleeping=sleeping)
        material_margins[offset] = ranked.material_margin
        object_margins[offset] = ranked.object_margin
        material_ok = deterministic or ranked.material_margin >= night_material_margin
        object_threshold = (
            night_object_absence_margin
            if ranked.state.object_name is None else
            night_object_presence_margin)
        object_ok = deterministic or ranked.object_margin >= object_threshold
        if material_ok:
          materials[offset] = ranked.state.material
        if offset == (0, 0):
          absent.add(offset)
        elif object_ok:
          if ranked.state.object_name is None:
            absent.add(offset)
          else:
            objects[offset] = ranked.state.object_name
            if ranked.state.direction is not None:
              directions[offset] = ranked.state.direction

    return VisualSymbolicObservation(
        materials=materials,
        objects=objects,
        object_absent=frozenset(absent),
        object_directions=directions,
        inventory=self.decode_hud(frame),
        facing=facing,
        sleeping=sleeping,
        material_margin=material_margins,
        object_margin=object_margins,
        step=step,
        reward=reward,
    )


__all__ = [
    "CARDINALS",
    "CellState",
    "CrafterRGBDecoder",
    "FRAME_SIZE",
    "ITEMS",
    "MATERIALS",
    "NIGHT_MATERIAL_MARGIN",
    "NIGHT_OBJECT_ABSENCE_MARGIN",
    "NIGHT_OBJECT_PRESENCE_MARGIN",
    "RankedCell",
    "daylight",
]
