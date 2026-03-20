#!/usr/bin/env python3
"""Generate hex terrain map for wargame scenarios.

Usage: python scripts/generate_hex_map.py [--width 15] [--height 12] [--output scripts/seed_scenarios/map.json]

Generates a default plain terrain grid, then overlays specific terrain features.
"""
import json
import argparse
import random
from pathlib import Path


def generate_base_grid(width: int, height: int) -> list[dict]:
    """Generate base grid of PLAIN hexes using offset-to-axial conversion."""
    hexes = []
    for row in range(height):
        for col in range(width):
            # Offset to axial: q = col - (row // 2), r = row
            q = col - (row // 2)
            r = row
            hexes.append({
                "q": q,
                "r": r,
                "terrain": "PLAIN",
                "elevation": 0,
                "movement_cost": 1,
                "defense_modifier": 1.0,
                "name": None,
            })
    return hexes


def apply_terrain_overlay(hexes: list[dict], overlays: list[dict]) -> list[dict]:
    """Apply terrain modifications to specific hexes.

    overlays: [{"q": 3, "r": 2, "terrain": "MOUNTAIN", "elevation": 500, ...}, ...]
    """
    hex_map = {(h["q"], h["r"]): h for h in hexes}
    for overlay in overlays:
        key = (overlay["q"], overlay["r"])
        if key in hex_map:
            hex_map[key].update(overlay)
    return list(hex_map.values())


# Korean Peninsula scenario terrain overlays
KOREAN_TERRAIN_OVERLAYS = [
    # Northern mountain range (rows 0-3)
    {"q": 0, "r": 0, "terrain": "MOUNTAIN", "elevation": 800, "movement_cost": 3, "defense_modifier": 1.5, "name": "Taebaek Range North"},
    {"q": 1, "r": 0, "terrain": "MOUNTAIN", "elevation": 700, "movement_cost": 3, "defense_modifier": 1.5},
    {"q": -1, "r": 1, "terrain": "MOUNTAIN", "elevation": 600, "movement_cost": 3, "defense_modifier": 1.5},
    {"q": 0, "r": 1, "terrain": "FOREST", "elevation": 400, "movement_cost": 2, "defense_modifier": 1.2},
    {"q": 2, "r": 0, "terrain": "FOREST", "elevation": 300, "movement_cost": 2, "defense_modifier": 1.2},
    # Central corridor (rows 4-7) - mix of urban and plains
    {"q": 2, "r": 4, "terrain": "URBAN", "elevation": 50, "movement_cost": 2, "defense_modifier": 2.0, "name": "Uijeongbu"},
    {"q": 3, "r": 5, "terrain": "URBAN", "elevation": 30, "movement_cost": 2, "defense_modifier": 2.0, "name": "Seoul"},
    {"q": 4, "r": 5, "terrain": "URBAN", "elevation": 30, "movement_cost": 2, "defense_modifier": 2.0, "name": "Seoul East"},
    # Rivers
    {"q": 1, "r": 6, "terrain": "RIVER", "elevation": 10, "movement_cost": 3, "defense_modifier": 1.3, "name": "Han River West"},
    {"q": 2, "r": 6, "terrain": "BRIDGE", "elevation": 10, "movement_cost": 1, "defense_modifier": 1.0, "name": "Han River Bridge"},
    {"q": 3, "r": 6, "terrain": "RIVER", "elevation": 10, "movement_cost": 3, "defense_modifier": 1.3, "name": "Han River East"},
    # Southern area (rows 8-11)
    {"q": 1, "r": 8, "terrain": "FOREST", "elevation": 200, "movement_cost": 2, "defense_modifier": 1.2},
    {"q": 3, "r": 9, "terrain": "URBAN", "elevation": 40, "movement_cost": 2, "defense_modifier": 2.0, "name": "Suwon"},
    # Western coast - water
    {"q": -2, "r": 3, "terrain": "WATER", "elevation": 0, "movement_cost": 999, "defense_modifier": 0.0},
    {"q": -3, "r": 4, "terrain": "WATER", "elevation": 0, "movement_cost": 999, "defense_modifier": 0.0},
    {"q": -2, "r": 5, "terrain": "WATER", "elevation": 0, "movement_cost": 999, "defense_modifier": 0.0},
    # Eastern mountains
    {"q": 7, "r": 2, "terrain": "MOUNTAIN", "elevation": 900, "movement_cost": 3, "defense_modifier": 1.5, "name": "Taebaek Range East"},
    {"q": 8, "r": 3, "terrain": "MOUNTAIN", "elevation": 700, "movement_cost": 3, "defense_modifier": 1.5},
]


def generate_korean_peninsula_scenario() -> dict:
    """Generate the full Korean Peninsula scenario JSON."""
    hexes = generate_base_grid(15, 12)
    hexes = apply_terrain_overlay(hexes, KOREAN_TERRAIN_OVERLAYS)

    return {
        "name": "Korean Peninsula Scenario",
        "description": "Central Korean Peninsula engagement - battalion-level modern warfare simulation",
        "map": {
            "width": 15,
            "height": 12,
            "hexes": hexes,
        },
        "forces": {
            "BLUE": {
                "name": "ROK/US Combined Forces",
                "units": [
                    # Theater HQ
                    {"id": "blue_combined_hq", "name": "Combined Forces HQ", "type": "HQ", "size": "DIVISION",
                     "position": {"q": 3, "r": 9}, "strength": 1.0, "morale": 0.9,
                     "max_movement_points": 2, "attack_power": 5.0, "defense_power": 10.0,
                     "effective_range": 1, "parent_unit_id": None,
                     "subordinate_ids": ["blue_1mech_1bn", "blue_1mech_2bn", "blue_1armor_bn", "blue_arty_bn"]},
                    # 1st Mechanized Infantry Battalion
                    {"id": "blue_1mech_1bn", "name": "1st Mech Infantry Bn", "type": "MECHANIZED", "size": "BATTALION",
                     "position": {"q": 2, "r": 5}, "strength": 1.0, "morale": 0.85,
                     "max_movement_points": 3, "attack_power": 18.0, "defense_power": 15.0,
                     "effective_range": 1, "parent_unit_id": "blue_combined_hq", "subordinate_ids": []},
                    # 2nd Mechanized Infantry Battalion
                    {"id": "blue_1mech_2bn", "name": "2nd Mech Infantry Bn", "type": "MECHANIZED", "size": "BATTALION",
                     "position": {"q": 4, "r": 5}, "strength": 1.0, "morale": 0.85,
                     "max_movement_points": 3, "attack_power": 18.0, "defense_power": 15.0,
                     "effective_range": 1, "parent_unit_id": "blue_combined_hq", "subordinate_ids": []},
                    # 1st Armor Battalion
                    {"id": "blue_1armor_bn", "name": "1st Armor Bn", "type": "ARMOR", "size": "BATTALION",
                     "position": {"q": 3, "r": 7}, "strength": 1.0, "morale": 0.8,
                     "max_movement_points": 4, "attack_power": 25.0, "defense_power": 12.0,
                     "effective_range": 1, "parent_unit_id": "blue_combined_hq", "subordinate_ids": []},
                    # Artillery Battalion
                    {"id": "blue_arty_bn", "name": "Artillery Bn", "type": "ARTILLERY", "size": "BATTALION",
                     "position": {"q": 3, "r": 8}, "strength": 1.0, "morale": 0.85,
                     "max_movement_points": 2, "attack_power": 20.0, "defense_power": 5.0,
                     "effective_range": 3, "parent_unit_id": "blue_combined_hq", "subordinate_ids": []},
                ],
                "commanders": [
                    {"id": "blue_theater_cmd", "name": "Gen. Kim", "rank": "Theater",
                     "unit_id": "blue_combined_hq", "personality_traits": {"aggression": 0.4, "caution": 0.6}},
                    {"id": "blue_1mech_1bn_cmd", "name": "LtCol. Park", "rank": "Battalion",
                     "unit_id": "blue_1mech_1bn", "personality_traits": {"aggression": 0.5, "caution": 0.5}},
                    {"id": "blue_1mech_2bn_cmd", "name": "LtCol. Lee", "rank": "Battalion",
                     "unit_id": "blue_1mech_2bn", "personality_traits": {"aggression": 0.5, "caution": 0.5}},
                    {"id": "blue_1armor_bn_cmd", "name": "LtCol. Choi", "rank": "Battalion",
                     "unit_id": "blue_1armor_bn", "personality_traits": {"aggression": 0.6, "caution": 0.4}},
                    {"id": "blue_arty_bn_cmd", "name": "LtCol. Jung", "rank": "Battalion",
                     "unit_id": "blue_arty_bn", "personality_traits": {"aggression": 0.3, "caution": 0.7}},
                ],
            },
            "RED": {
                "name": "DPRK Forces",
                "units": [
                    # Theater HQ
                    {"id": "red_combined_hq", "name": "DPRK Command", "type": "HQ", "size": "DIVISION",
                     "position": {"q": 1, "r": 1}, "strength": 1.0, "morale": 0.85,
                     "max_movement_points": 2, "attack_power": 5.0, "defense_power": 10.0,
                     "effective_range": 1, "parent_unit_id": None,
                     "subordinate_ids": ["red_1inf_1bn", "red_1inf_2bn", "red_1armor_bn", "red_arty_bn"]},
                    # 1st Infantry Battalion
                    {"id": "red_1inf_1bn", "name": "1st Infantry Bn", "type": "INFANTRY", "size": "BATTALION",
                     "position": {"q": 1, "r": 3}, "strength": 1.0, "morale": 0.8,
                     "max_movement_points": 2, "attack_power": 12.0, "defense_power": 14.0,
                     "effective_range": 1, "parent_unit_id": "red_combined_hq", "subordinate_ids": []},
                    # 2nd Infantry Battalion
                    {"id": "red_1inf_2bn", "name": "2nd Infantry Bn", "type": "INFANTRY", "size": "BATTALION",
                     "position": {"q": 3, "r": 2}, "strength": 1.0, "morale": 0.8,
                     "max_movement_points": 2, "attack_power": 12.0, "defense_power": 14.0,
                     "effective_range": 1, "parent_unit_id": "red_combined_hq", "subordinate_ids": []},
                    # Armor Battalion
                    {"id": "red_1armor_bn", "name": "T-72 Armor Bn", "type": "ARMOR", "size": "BATTALION",
                     "position": {"q": 2, "r": 2}, "strength": 1.0, "morale": 0.75,
                     "max_movement_points": 4, "attack_power": 22.0, "defense_power": 10.0,
                     "effective_range": 1, "parent_unit_id": "red_combined_hq", "subordinate_ids": []},
                    # Artillery Battalion
                    {"id": "red_arty_bn", "name": "Artillery Bn", "type": "ARTILLERY", "size": "BATTALION",
                     "position": {"q": 1, "r": 1}, "strength": 1.0, "morale": 0.8,
                     "max_movement_points": 2, "attack_power": 18.0, "defense_power": 5.0,
                     "effective_range": 3, "parent_unit_id": "red_combined_hq", "subordinate_ids": []},
                ],
                "commanders": [
                    {"id": "red_theater_cmd", "name": "Gen. Pak", "rank": "Theater",
                     "unit_id": "red_combined_hq", "personality_traits": {"aggression": 0.7, "caution": 0.3}},
                    {"id": "red_1inf_1bn_cmd", "name": "Col. Ri", "rank": "Battalion",
                     "unit_id": "red_1inf_1bn", "personality_traits": {"aggression": 0.6, "caution": 0.4}},
                    {"id": "red_1inf_2bn_cmd", "name": "Col. Kim", "rank": "Battalion",
                     "unit_id": "red_1inf_2bn", "personality_traits": {"aggression": 0.6, "caution": 0.4}},
                    {"id": "red_1armor_bn_cmd", "name": "Col. Choe", "rank": "Battalion",
                     "unit_id": "red_1armor_bn", "personality_traits": {"aggression": 0.7, "caution": 0.3}},
                    {"id": "red_arty_bn_cmd", "name": "Col. Han", "rank": "Battalion",
                     "unit_id": "red_arty_bn", "personality_traits": {"aggression": 0.4, "caution": 0.6}},
                ],
            },
        },
        "relationships": [
            # BLUE command chain
            {"source": "blue_theater_cmd", "target": "blue_combined_hq", "type": "COMMANDS"},
            {"source": "blue_theater_cmd", "target": "blue_1mech_1bn", "type": "COMMANDS"},
            {"source": "blue_theater_cmd", "target": "blue_1mech_2bn", "type": "COMMANDS"},
            {"source": "blue_theater_cmd", "target": "blue_1armor_bn", "type": "COMMANDS"},
            {"source": "blue_theater_cmd", "target": "blue_arty_bn", "type": "COMMANDS"},
            # BLUE force membership
            {"source": "blue_combined_hq", "target": "BLUE", "type": "BELONGS_TO"},
            {"source": "blue_1mech_1bn", "target": "BLUE", "type": "BELONGS_TO"},
            {"source": "blue_1mech_2bn", "target": "BLUE", "type": "BELONGS_TO"},
            {"source": "blue_1armor_bn", "target": "BLUE", "type": "BELONGS_TO"},
            {"source": "blue_arty_bn", "target": "BLUE", "type": "BELONGS_TO"},
            # BLUE supply routes
            {"source": "blue_msr_1", "target": "blue_1mech_1bn", "type": "SUPPLIES"},
            {"source": "blue_msr_1", "target": "blue_1mech_2bn", "type": "SUPPLIES"},
            {"source": "blue_msr_1", "target": "blue_1armor_bn", "type": "SUPPLIES"},
            {"source": "blue_msr_1", "target": "blue_arty_bn", "type": "SUPPLIES"},
            {"source": "blue_msr_1", "target": "bridge_han", "type": "PASSES_THROUGH"},
            # RED command chain
            {"source": "red_theater_cmd", "target": "red_combined_hq", "type": "COMMANDS"},
            {"source": "red_theater_cmd", "target": "red_1inf_1bn", "type": "COMMANDS"},
            {"source": "red_theater_cmd", "target": "red_1inf_2bn", "type": "COMMANDS"},
            {"source": "red_theater_cmd", "target": "red_1armor_bn", "type": "COMMANDS"},
            {"source": "red_theater_cmd", "target": "red_arty_bn", "type": "COMMANDS"},
            # RED force membership
            {"source": "red_combined_hq", "target": "RED", "type": "BELONGS_TO"},
            {"source": "red_1inf_1bn", "target": "RED", "type": "BELONGS_TO"},
            {"source": "red_1inf_2bn", "target": "RED", "type": "BELONGS_TO"},
            {"source": "red_1armor_bn", "target": "RED", "type": "BELONGS_TO"},
            {"source": "red_arty_bn", "target": "RED", "type": "BELONGS_TO"},
            # RED supply routes
            {"source": "red_msr_1", "target": "red_1inf_1bn", "type": "SUPPLIES"},
            {"source": "red_msr_1", "target": "red_1inf_2bn", "type": "SUPPLIES"},
            {"source": "red_msr_1", "target": "red_1armor_bn", "type": "SUPPLIES"},
            {"source": "red_msr_1", "target": "red_arty_bn", "type": "SUPPLIES"},
        ],
        "victory_conditions": {
            "BLUE": {"hold_hexes": [{"q": 3, "r": 5}], "max_turns": 72, "enemy_strength_threshold": 0.3},
            "RED": {"capture_hexes": [{"q": 3, "r": 5}], "by_turn": 72, "enemy_strength_threshold": 0.3},
        },
        "config": {
            "turn_duration_hours": 2,
            "hex_scale_km": 10,
            "max_turns": 72,
        },
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate hex terrain map")
    parser.add_argument("--output", default="scripts/seed_scenarios/korean_peninsula.json")
    args = parser.parse_args()

    scenario = generate_korean_peninsula_scenario()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(scenario, f, indent=2, ensure_ascii=False)

    print(f"Generated scenario: {output_path}")
    print(f"  Map: {scenario['map']['width']}x{scenario['map']['height']} = {len(scenario['map']['hexes'])} hexes")
    print(f"  BLUE: {len(scenario['forces']['BLUE']['units'])} units, {len(scenario['forces']['BLUE']['commanders'])} commanders")
    print(f"  RED: {len(scenario['forces']['RED']['units'])} units, {len(scenario['forces']['RED']['commanders'])} commanders")
    print(f"  Relationships: {len(scenario['relationships'])}")
