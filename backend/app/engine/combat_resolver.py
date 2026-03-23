from __future__ import annotations
import random
from app.models.domain import Unit, TerrainHex, TerrainType, UnitType
from app.models.simulation import CombatResult, CombatOutcome
from app.models.supply import SupplyLevel, SupplyStatus

RATIO_CATEGORIES = ["1:3", "1:2", "1:1", "2:1", "3:1", "5:1"]
CRT_MATRIX = [
    # d1    d2    d3    d4    d5    d6
    ["AR", "AR", "AR", "S",  "S",  "DR"],   # 1:3
    ["AR", "AR", "S",  "S",  "DR", "DR"],   # 1:2
    ["AR", "S",  "S",  "DR", "DR", "DE"],   # 1:1
    ["S",  "S",  "DR", "DR", "DE", "DE"],   # 2:1
    ["S",  "DR", "DE", "DE", "DE", "DRt"],  # 3:1
    ["DR", "DE", "DE", "DRt","DRt","DRt"],  # 5:1
]

RESULT_MAP = {
    "AR": CombatResult.ATTACKER_RETREAT,
    "S": CombatResult.STALEMATE,
    "DR": CombatResult.DEFENDER_RETREAT,
    "DE": CombatResult.DEFENDER_EXPELLED,
    "DRt": CombatResult.DEFENDER_ROUT,
}

CRT_TABLE: dict[tuple[str, int], CombatResult] = {}
for _i, _ratio in enumerate(RATIO_CATEGORIES):
    for _die in range(6):
        CRT_TABLE[(_ratio, _die + 1)] = RESULT_MAP[CRT_MATRIX[_i][_die]]

# (atk_loss, def_loss, atk_retreat_hexes, def_retreat_hexes)
LOSS_TABLE: dict[CombatResult, tuple[float, float, int, int]] = {
    CombatResult.ATTACKER_RETREAT: (0.10, 0.0,  1, 0),
    CombatResult.STALEMATE:        (0.10, 0.10, 0, 0),
    CombatResult.DEFENDER_RETREAT: (0.05, 0.15, 0, 1),
    CombatResult.DEFENDER_EXPELLED:(0.05, 0.25, 0, 2),
    CombatResult.DEFENDER_ROUT:    (0.05, 0.40, 0, 3),
}

_RESULT_DESCRIPTIONS = {
    CombatResult.ATTACKER_RETREAT: "Attacker forced to withdraw",
    CombatResult.STALEMATE:        "Engagement ends in stalemate",
    CombatResult.DEFENDER_RETREAT: "Defender falls back under pressure",
    CombatResult.DEFENDER_EXPELLED:"Defender expelled from position",
    CombatResult.DEFENDER_ROUT:    "Defender routed in disarray",
}


def classify_force_ratio(ratio: float) -> str:
    if ratio <= 0.33:
        return "1:3"
    elif ratio <= 0.66:
        return "1:2"
    elif ratio <= 1.5:
        return "1:1"
    elif ratio <= 2.5:
        return "2:1"
    elif ratio <= 4.0:
        return "3:1"
    else:
        return "5:1"


def terrain_defense_modifier(terrain: TerrainHex, defender_type: UnitType) -> float:
    if terrain.terrain_type == TerrainType.URBAN:
        if defender_type in (UnitType.INFANTRY, UnitType.MECHANIZED):
            return 2.0
        return terrain.defense_modifier
    if terrain.terrain_type == TerrainType.MOUNTAIN:
        return 1.5
    return terrain.defense_modifier


def terrain_attack_modifier(terrain: TerrainHex, attacker_type: UnitType) -> float:
    if terrain.terrain_type == TerrainType.URBAN and attacker_type == UnitType.ARMOR:
        return 0.5
    return 1.0


def supply_modifier(unit: Unit) -> float:
    return 0.5 if unit.ammo < 0.3 else 1.0


_SUPPLY_LEVEL_MODIFIER: dict[SupplyLevel, float] = {
    SupplyLevel.FULL: 1.0,
    SupplyLevel.REDUCED: 0.8,
    SupplyLevel.CUT_OFF: 0.5,
}


def supply_status_modifier(unit: Unit, supply_status_map: dict[str, SupplyStatus]) -> float:
    """Return combat modifier based on SupplyStatus when supply tracking is active."""
    status = supply_status_map.get(unit.id)
    if status is None:
        return 1.0
    return _SUPPLY_LEVEL_MODIFIER[status.level]


def morale_modifier(unit: Unit) -> float:
    return 0.6 if unit.morale < 0.3 else 1.0


class CombatResolver:
    def __init__(self, rng_seed: int | None = None):
        self.rng = random.Random(rng_seed)

    def resolve_combat(
        self,
        attackers: list[Unit],
        defenders: list[Unit],
        terrain: TerrainHex,
        cas_modifier: float = 0.0,
        supply_status_map: dict[str, SupplyStatus] | None = None,
    ) -> CombatOutcome:
        atk_power = self._calculate_attack_power(attackers, terrain, supply_status_map)
        effective_attack = atk_power * (1.0 + cas_modifier)
        def_power = self._calculate_defense_power(defenders, terrain, supply_status_map)

        if def_power <= 0:
            def_power = 0.01

        force_ratio = effective_attack / def_power
        ratio_cat = classify_force_ratio(force_ratio)
        die_roll = self.rng.randint(1, 6)
        result = CRT_TABLE[(ratio_cat, die_roll)]

        atk_loss, def_loss, _atk_retreat, def_retreat = LOSS_TABLE[result]

        return CombatOutcome(
            attacker_id=attackers[0].id,
            defender_id=defenders[0].id,
            hex_coord=defenders[0].position,
            force_ratio=round(force_ratio, 2),
            die_roll=die_roll,
            result=result,
            attacker_losses=atk_loss,
            defender_losses=def_loss,
            defender_retreat_hexes=def_retreat,
            narrative=self._generate_narrative(attackers, defenders, result, force_ratio),
        )

    def _calculate_attack_power(
        self,
        attackers: list[Unit],
        terrain: TerrainHex,
        supply_status_map: dict[str, SupplyStatus] | None = None,
    ) -> float:
        total = 0.0
        for unit in attackers:
            power = unit.attack_power * unit.strength
            if supply_status_map is not None:
                power *= supply_status_modifier(unit, supply_status_map)
            else:
                power *= supply_modifier(unit)
            power *= morale_modifier(unit)
            power *= terrain_attack_modifier(terrain, unit.unit_type)
            total += power
        return total

    def _calculate_defense_power(
        self,
        defenders: list[Unit],
        terrain: TerrainHex,
        supply_status_map: dict[str, SupplyStatus] | None = None,
    ) -> float:
        total = 0.0
        for unit in defenders:
            power = unit.defense_power * unit.strength
            if supply_status_map is not None:
                power *= supply_status_modifier(unit, supply_status_map)
            else:
                power *= supply_modifier(unit)
            power *= morale_modifier(unit)
            power *= terrain_defense_modifier(terrain, unit.unit_type)
            total += power
        return total

    def _generate_narrative(
        self,
        attackers: list[Unit],
        defenders: list[Unit],
        result: CombatResult,
        ratio: float,
    ) -> str:
        description = _RESULT_DESCRIPTIONS.get(result, str(result))
        return (
            f"{attackers[0].name} vs {defenders[0].name} "
            f"(ratio {ratio:.1f}:1) - {description}"
        )
