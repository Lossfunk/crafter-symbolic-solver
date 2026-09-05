"""Small public boundary: exact RGB in, one integer action out."""
import numpy as np

from ._policy.config import ACTION_NAMES
from ._policy.symbolic_expedition_agent import ExpeditionAgent
from ._policy.symbolic_opportunity_agent import OpportunityAgent


class Agent:
    """One autonomous controller with episode-local symbolic memory.

    ``pocket`` is the recommended release. ``combined`` retains exactly the
    same pre-diamond controller and omits the natural crop-pocket extension.
    Call once per returned observation, starting at reset. Do not supply info,
    re-rendered images, batched frames, action repeats, or simulator objects.
    """
    def __init__(self, variant='pocket'):
        if variant not in ('pocket', 'combined'):
            raise ValueError("variant must be 'pocket' or 'combined'")
        self.variant = variant
        self._controller = (ExpeditionAgent(pocket=True) if variant == 'pocket' else
                            OpportunityAgent(food_distance=6, forge_return=True, combat=True))

    def reset(self):
        """Clear all episode history while preserving the chosen variant."""
        self._controller.reset()

    @property
    def steps(self):
        return self._controller.step

    def act(self, rgb, reward=0.0):
        """Return an integer in [0,16] for the exact uint8 64x64x3 frame."""
        if not isinstance(rgb, np.ndarray) or rgb.shape != (64, 64, 3) or rgb.dtype != np.uint8:
            raise ValueError('Expected exact Crafter RGB: numpy uint8 array, shape (64, 64, 3)')
        name = self._controller.act(rgb, float(reward))
        return ACTION_NAMES.index(name)
