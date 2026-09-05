"""Exact measured action order and configuration; no legacy oracle API."""
from typing import Any

ACTION_NAMES = (
    "noop",
    "move_left",
    "move_right",
    "move_up",
    "move_down",
    "do",
    "sleep",
    "place_stone",
    "place_table",
    "place_furnace",
    "place_plant",
    "make_wood_pickaxe",
    "make_stone_pickaxe",
    "make_iron_pickaxe",
    "make_wood_sword",
    "make_stone_sword",
    "make_iron_sword",
)

FINAL_CONFIG: dict[str, Any] = {
    "craft_stone_sword": True,
    "shelter_light": 0.40,
    "food_hunt_level": 5,
    "local_shelter": True,
    "shelter_exit_light": 0.75,
    "drink_seek_level": 4,
    "finish_known_diamond": True,
    "defer_last_wood_if_cost_le": 4,
    "directed_mountain_frontier": True,
    "avoid_arrow_health": 2,
    "revalidate_reused_shelter": True,
    "critical_risk_veto_health": 1,
    "systematic_mountain_after": 300,
    "systematic_mountain_neighbor_weight": 4,
    "systematic_mountain_kernel_radius": 5,
    "systematic_mountain_persistent": False,
    "score_fast_iron_sword_cost": 19,
    "score_iron_before_wood": True,
}
