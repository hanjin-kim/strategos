from __future__ import annotations
import pytest
from app.models.domain import (
    HexCoord, Side, UnitType, UnitSize, UnitStatus, TerrainHex, TerrainType, Unit
)
from app.models.simulation import CombatResult
from app.engine.combat_resolver import (
    CRT_TABLE,
    classify_force_ratio,
    terrain_defense_modifier,
    terrain_attack_modifier,
    supply_modifier,
    morale_modifier,
    CombatResolver,
    LOSS_TABLE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_unit(
    *,
    uid: str = "u1",
    name: str = "Unit",
    side: Side = Side.BLUE,
    unit_type: UnitType = UnitType.INFANTRY,
    position: HexCoord = HexCoord(q=0, r=0),
    strength: float = 1.0,
    morale: float = 1.0,
    attack_power: float = 10.0,
    defense_power: float = 10.0,
    ammo: float = 1.0,
    fuel: float = 1.0,
) -> Unit:
    return Unit(
        id=uid,
        name=name,
        side=side,
        unit_type=unit_type,
        size=UnitSize.BATTALION,
        position=position,
        strength=strength,
        morale=morale,
        movement_points=4,
        max_movement_points=4,
        attack_power=attack_power,
        defense_power=defense_power,
        effective_range=1,
        ammo=ammo,
        fuel=fuel,
        status=UnitStatus.ACTIVE,
    )


def make_terrain(terrain_type: TerrainType = TerrainType.PLAIN, defense_modifier: float = 1.0) -> TerrainHex:
    return TerrainHex(
        coord=HexCoord(q=0, r=0),
        terrain_type=terrain_type,
        defense_modifier=defense_modifier,
    )


# ---------------------------------------------------------------------------
# 1. classify_force_ratio: all 6 categories with boundary values
# ---------------------------------------------------------------------------

class TestClassifyForceRatio:
    def test_1_3_at_boundary(self):
        assert classify_force_ratio(0.33) == "1:3"

    def test_1_3_well_below(self):
        assert classify_force_ratio(0.1) == "1:3"

    def test_1_2_just_above_boundary(self):
        assert classify_force_ratio(0.34) == "1:2"

    def test_1_2_at_boundary(self):
        assert classify_force_ratio(0.66) == "1:2"

    def test_1_1_just_above(self):
        assert classify_force_ratio(0.67) == "1:1"

    def test_1_1_at_boundary(self):
        assert classify_force_ratio(1.5) == "1:1"

    def test_2_1_just_above(self):
        assert classify_force_ratio(1.51) == "2:1"

    def test_2_1_at_boundary(self):
        assert classify_force_ratio(2.5) == "2:1"

    def test_3_1_just_above(self):
        assert classify_force_ratio(2.51) == "3:1"

    def test_3_1_at_boundary(self):
        assert classify_force_ratio(4.0) == "3:1"

    def test_5_1_just_above(self):
        assert classify_force_ratio(4.01) == "5:1"

    def test_5_1_large(self):
        assert classify_force_ratio(100.0) == "5:1"


# ---------------------------------------------------------------------------
# 2. CRT_TABLE completeness: 6 ratios x 6 dice = 36 entries
# ---------------------------------------------------------------------------

def test_crt_table_has_36_entries():
    assert len(CRT_TABLE) == 36


def test_crt_table_all_valid_results():
    valid = set(CombatResult)
    for result in CRT_TABLE.values():
        assert result in valid


# ---------------------------------------------------------------------------
# 3. terrain_defense_modifier
# ---------------------------------------------------------------------------

class TestTerrainDefenseModifier:
    def test_urban_infantry_is_2(self):
        t = make_terrain(TerrainType.URBAN)
        assert terrain_defense_modifier(t, UnitType.INFANTRY) == 2.0

    def test_urban_mechanized_is_2(self):
        t = make_terrain(TerrainType.URBAN)
        assert terrain_defense_modifier(t, UnitType.MECHANIZED) == 2.0

    def test_urban_armor_uses_terrain_default(self):
        t = make_terrain(TerrainType.URBAN, defense_modifier=2.0)
        assert terrain_defense_modifier(t, UnitType.ARMOR) == 2.0

    def test_mountain_is_1_5(self):
        t = make_terrain(TerrainType.MOUNTAIN)
        assert terrain_defense_modifier(t, UnitType.INFANTRY) == 1.5

    def test_plain_is_default(self):
        t = make_terrain(TerrainType.PLAIN, defense_modifier=1.0)
        assert terrain_defense_modifier(t, UnitType.INFANTRY) == 1.0

    def test_forest_uses_terrain_modifier(self):
        t = make_terrain(TerrainType.FOREST, defense_modifier=1.2)
        assert terrain_defense_modifier(t, UnitType.INFANTRY) == 1.2


# ---------------------------------------------------------------------------
# 4. terrain_attack_modifier
# ---------------------------------------------------------------------------

class TestTerrainAttackModifier:
    def test_urban_armor_is_0_5(self):
        t = make_terrain(TerrainType.URBAN)
        assert terrain_attack_modifier(t, UnitType.ARMOR) == 0.5

    def test_urban_infantry_is_1(self):
        t = make_terrain(TerrainType.URBAN)
        assert terrain_attack_modifier(t, UnitType.INFANTRY) == 1.0

    def test_plain_armor_is_1(self):
        t = make_terrain(TerrainType.PLAIN)
        assert terrain_attack_modifier(t, UnitType.ARMOR) == 1.0

    def test_mountain_infantry_is_1(self):
        t = make_terrain(TerrainType.MOUNTAIN)
        assert terrain_attack_modifier(t, UnitType.INFANTRY) == 1.0


# ---------------------------------------------------------------------------
# 5. supply_modifier
# ---------------------------------------------------------------------------

class TestSupplyModifier:
    def test_low_ammo_returns_half(self):
        unit = make_unit(ammo=0.2)
        assert supply_modifier(unit) == 0.5

    def test_ammo_exactly_0_3_returns_half(self):
        # 0.3 is the threshold; < 0.3 triggers penalty
        unit = make_unit(ammo=0.3)
        assert supply_modifier(unit) == 1.0

    def test_normal_ammo_returns_1(self):
        unit = make_unit(ammo=0.8)
        assert supply_modifier(unit) == 1.0

    def test_zero_ammo_returns_half(self):
        unit = make_unit(ammo=0.0)
        assert supply_modifier(unit) == 0.5


# ---------------------------------------------------------------------------
# 6. morale_modifier
# ---------------------------------------------------------------------------

class TestMoraleModifier:
    def test_low_morale_returns_0_6(self):
        unit = make_unit(morale=0.1)
        assert morale_modifier(unit) == 0.6

    def test_morale_exactly_0_3_returns_1(self):
        unit = make_unit(morale=0.3)
        assert morale_modifier(unit) == 1.0

    def test_normal_morale_returns_1(self):
        unit = make_unit(morale=0.8)
        assert morale_modifier(unit) == 1.0

    def test_zero_morale_returns_0_6(self):
        unit = make_unit(morale=0.0)
        assert morale_modifier(unit) == 0.6


# ---------------------------------------------------------------------------
# 7. resolve_combat with seeded RNG: predictable result
# ---------------------------------------------------------------------------

def test_resolve_combat_seeded_rng_is_deterministic():
    resolver_a = CombatResolver(rng_seed=42)
    resolver_b = CombatResolver(rng_seed=42)
    terrain = make_terrain()
    atk = [make_unit(uid="a1", name="Alpha", attack_power=20.0)]
    dfn = [make_unit(uid="d1", name="Delta", side=Side.RED, defense_power=10.0)]
    result_a = resolver_a.resolve_combat(atk, dfn, terrain)
    result_b = resolver_b.resolve_combat(atk, dfn, terrain)
    assert result_a == result_b


# ---------------------------------------------------------------------------
# 8. resolve_combat: 3:1 ratio + die=6 -> DRt
# ---------------------------------------------------------------------------

def test_3_1_die6_is_defender_rout():
    # force_ratio ~3.0 -> "3:1"; need rng to produce 6
    # Use seed that yields die=6 for first roll, or mock via subclass
    class FixedDie6(CombatResolver):
        def __init__(self):
            super().__init__()
            self.rng = _FixedRNG(6)

    resolver = FixedDie6()
    terrain = make_terrain()
    # attack_power=30 / defense_power=10 -> ratio=3.0 -> "3:1"
    atk = [make_unit(uid="a1", name="Attacker", attack_power=30.0, defense_power=1.0)]
    dfn = [make_unit(uid="d1", name="Defender", side=Side.RED, defense_power=10.0, attack_power=1.0)]
    outcome = resolver.resolve_combat(atk, dfn, terrain)
    assert outcome.result == CombatResult.DEFENDER_ROUT


# ---------------------------------------------------------------------------
# 9. resolve_combat: 1:3 ratio + die=1 -> AR
# ---------------------------------------------------------------------------

def test_1_3_die1_is_attacker_retreat():
    class FixedDie1(CombatResolver):
        def __init__(self):
            super().__init__()
            self.rng = _FixedRNG(1)

    resolver = FixedDie1()
    terrain = make_terrain()
    # attack_power=5 / defense_power=20 -> ratio=0.25 -> "1:3"
    atk = [make_unit(uid="a1", name="Attacker", attack_power=5.0, defense_power=1.0)]
    dfn = [make_unit(uid="d1", name="Defender", side=Side.RED, defense_power=20.0, attack_power=1.0)]
    outcome = resolver.resolve_combat(atk, dfn, terrain)
    assert outcome.result == CombatResult.ATTACKER_RETREAT


# ---------------------------------------------------------------------------
# 10. resolve_combat: urban defense doubles infantry defense power
# ---------------------------------------------------------------------------

def test_urban_doubles_infantry_defense():
    resolver = CombatResolver(rng_seed=0)
    plain_terrain = make_terrain(TerrainType.PLAIN)
    urban_terrain = make_terrain(TerrainType.URBAN)

    # With same attack, urban defender has 2x defense -> lower force ratio -> worse attacker result
    atk = [make_unit(uid="a1", name="Attacker", attack_power=20.0)]
    dfn_plain = [make_unit(uid="d1", name="Defender", side=Side.RED, defense_power=10.0)]
    dfn_urban = [make_unit(uid="d2", name="Defender", side=Side.RED, defense_power=10.0, unit_type=UnitType.INFANTRY)]

    # plain: ratio = 20/10 = 2.0 -> "2:1"
    # urban: ratio = 20/20 = 1.0 -> "1:1"
    resolver_plain = CombatResolver(rng_seed=0)
    resolver_urban = CombatResolver(rng_seed=0)
    outcome_plain = resolver_plain.resolve_combat(atk, dfn_plain, plain_terrain)
    outcome_urban = resolver_urban.resolve_combat(atk, dfn_urban, urban_terrain)

    assert outcome_plain.force_ratio == 2.0
    assert outcome_urban.force_ratio == 1.0


# ---------------------------------------------------------------------------
# 11. resolve_combat: low ammo halves combat power
# ---------------------------------------------------------------------------

def test_low_ammo_halves_attack_power():
    resolver_normal = CombatResolver(rng_seed=7)
    resolver_low = CombatResolver(rng_seed=7)
    terrain = make_terrain()

    atk_normal = [make_unit(uid="a1", name="Attacker", attack_power=20.0, ammo=1.0)]
    atk_low    = [make_unit(uid="a1", name="Attacker", attack_power=20.0, ammo=0.1)]
    dfn = [make_unit(uid="d1", name="Defender", side=Side.RED, defense_power=10.0)]

    # normal: ratio = 20/10 = 2.0
    # low ammo: ratio = 10/10 = 1.0
    outcome_normal = resolver_normal.resolve_combat(atk_normal, dfn, terrain)
    outcome_low    = resolver_low.resolve_combat(atk_low, dfn, terrain)

    assert outcome_normal.force_ratio == 2.0
    assert outcome_low.force_ratio == 1.0


# ---------------------------------------------------------------------------
# 12. Loss values match CRT
# ---------------------------------------------------------------------------

class TestLossValues:
    def test_stalemate_losses(self):
        atk_loss, def_loss, _, _ = LOSS_TABLE[CombatResult.STALEMATE]
        assert atk_loss == pytest.approx(0.10)
        assert def_loss == pytest.approx(0.10)

    def test_defender_retreat_losses(self):
        atk_loss, def_loss, _, _ = LOSS_TABLE[CombatResult.DEFENDER_RETREAT]
        assert atk_loss == pytest.approx(0.05)
        assert def_loss == pytest.approx(0.15)

    def test_defender_expelled_losses(self):
        atk_loss, def_loss, _, _ = LOSS_TABLE[CombatResult.DEFENDER_EXPELLED]
        assert atk_loss == pytest.approx(0.05)
        assert def_loss == pytest.approx(0.25)

    def test_defender_rout_losses(self):
        atk_loss, def_loss, _, _ = LOSS_TABLE[CombatResult.DEFENDER_ROUT]
        assert atk_loss == pytest.approx(0.05)
        assert def_loss == pytest.approx(0.40)

    def test_attacker_retreat_losses(self):
        atk_loss, def_loss, _, _ = LOSS_TABLE[CombatResult.ATTACKER_RETREAT]
        assert atk_loss == pytest.approx(0.10)
        assert def_loss == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# 13. Narrative contains attacker/defender names
# ---------------------------------------------------------------------------

def test_narrative_contains_unit_names():
    resolver = CombatResolver(rng_seed=1)
    terrain = make_terrain()
    atk = [make_unit(uid="a1", name="1st Infantry")]
    dfn = [make_unit(uid="d1", name="2nd Armor", side=Side.RED)]
    outcome = resolver.resolve_combat(atk, dfn, terrain)
    assert "1st Infantry" in outcome.narrative
    assert "2nd Armor" in outcome.narrative


# ---------------------------------------------------------------------------
# 14. Multiple attackers: powers sum correctly
# ---------------------------------------------------------------------------

def test_multiple_attackers_sum_power():
    # Two attackers each with attack_power=10 should equal one attacker with 20
    resolver_single = CombatResolver(rng_seed=3)
    resolver_multi  = CombatResolver(rng_seed=3)
    terrain = make_terrain()

    atk_single = [make_unit(uid="a1", name="Alpha", attack_power=20.0)]
    atk_multi  = [
        make_unit(uid="a1", name="Alpha", attack_power=10.0),
        make_unit(uid="a2", name="Bravo", attack_power=10.0),
    ]
    dfn = [make_unit(uid="d1", name="Delta", side=Side.RED, defense_power=10.0)]

    outcome_single = resolver_single.resolve_combat(atk_single, dfn, terrain)
    outcome_multi  = resolver_multi.resolve_combat(atk_multi, dfn, terrain)

    assert outcome_single.force_ratio == outcome_multi.force_ratio
    assert outcome_single.result == outcome_multi.result


# ---------------------------------------------------------------------------
# Helper: fixed RNG that always returns the same value
# ---------------------------------------------------------------------------

class _FixedRNG:
    def __init__(self, value: int):
        self._value = value

    def randint(self, _a: int, _b: int) -> int:
        return self._value
