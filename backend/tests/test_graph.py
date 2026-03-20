from __future__ import annotations

import pytest

from app.graph.military_ontology import EntityType, RelationType, RELATION_CONSTRAINTS
from app.graph.relationship_graph import RelationshipGraph
from app.graph.graph_tools import GraphTools
from app.models.domain import HexCoord, Side, UnitType, UnitSize, UnitStatus, Unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_graph() -> RelationshipGraph:
    """Build a standard test graph with known entities and relationships."""
    g = RelationshipGraph()

    # Entities
    g.add_entity("blue_force", EntityType.FORCE, {"name": "Blue Force"})
    g.add_entity("blue_cmd", EntityType.COMMANDER, {"side": "BLUE", "rank": "Division"})
    g.add_entity("blue_1bn", EntityType.UNIT, {"side": "BLUE", "type": "INFANTRY"})
    g.add_entity("blue_2bn", EntityType.UNIT, {"side": "BLUE", "type": "INFANTRY"})
    g.add_entity("red_1bn", EntityType.UNIT, {"side": "RED", "type": "MECHANIZED"})
    g.add_entity("msr_1", EntityType.SUPPLY_ROUTE)
    g.add_entity("bridge_alpha", EntityType.TERRAIN_FEATURE)
    g.add_entity("blue_arty", EntityType.UNIT, {"side": "BLUE", "type": "ARTILLERY"})

    # Relationships
    g.add_relationship("blue_cmd", "blue_1bn", RelationType.COMMANDS)
    g.add_relationship("blue_cmd", "blue_2bn", RelationType.COMMANDS)
    g.add_relationship("blue_1bn", "blue_force", RelationType.BELONGS_TO)
    g.add_relationship("msr_1", "blue_1bn", RelationType.SUPPLIES)
    g.add_relationship("msr_1", "bridge_alpha", RelationType.PASSES_THROUGH)

    return g


def make_unit(uid: str, side: Side, q: int, r: int, unit_type: UnitType = UnitType.INFANTRY) -> Unit:
    return Unit(
        id=uid,
        name=uid,
        side=side,
        unit_type=unit_type,
        size=UnitSize.BATTALION,
        position=HexCoord(q=q, r=r),
        strength=1.0,
        morale=1.0,
        movement_points=4,
        max_movement_points=4,
        attack_power=1.0,
        defense_power=1.0,
        effective_range=2,
        ammo=1.0,
        fuel=1.0,
        status=UnitStatus.ACTIVE,
    )


class MockGameState:
    def __init__(self, units: dict):
        self.units = units


# ---------------------------------------------------------------------------
# 1. Ontology: all entity types and relation types exist
# ---------------------------------------------------------------------------

def test_all_entity_types_exist() -> None:
    expected = {
        "Force", "Unit", "Commander", "WeaponSystem",
        "Installation", "TerrainFeature", "SupplyRoute", "AirAsset",
    }
    assert {e.value for e in EntityType} == expected


def test_all_relation_types_exist() -> None:
    expected = {
        "COMMANDS", "BELONGS_TO", "EQUIPPED_WITH", "LOCATED_AT",
        "ADJACENT_TO", "SUPPLIES", "PASSES_THROUGH", "SUPPORTS",
        "THREATENS", "PROTECTS", "COVERS",
    }
    assert {r.value for r in RelationType} == expected


# ---------------------------------------------------------------------------
# 2. RELATION_CONSTRAINTS: every relation has valid source/target types
# ---------------------------------------------------------------------------

def test_relation_constraints_cover_all_relations() -> None:
    for rel_type in RelationType:
        assert rel_type in RELATION_CONSTRAINTS, f"{rel_type} missing from RELATION_CONSTRAINTS"


def test_relation_constraints_types_are_entity_type_sets() -> None:
    for rel_type, (sources, targets) in RELATION_CONSTRAINTS.items():
        assert isinstance(sources, set), f"{rel_type} sources not a set"
        assert isinstance(targets, set), f"{rel_type} targets not a set"
        for et in sources | targets:
            assert isinstance(et, EntityType), f"{et} is not an EntityType"


# ---------------------------------------------------------------------------
# 3. RelationshipGraph: add_entity, has_entity, remove_entity
# ---------------------------------------------------------------------------

def test_add_and_has_entity() -> None:
    g = RelationshipGraph()
    g.add_entity("unit_a", EntityType.UNIT)
    assert g.has_entity("unit_a")
    assert not g.has_entity("unit_b")


def test_remove_entity() -> None:
    g = RelationshipGraph()
    g.add_entity("unit_a", EntityType.UNIT)
    g.remove_entity("unit_a")
    assert not g.has_entity("unit_a")


def test_remove_nonexistent_entity_no_error() -> None:
    g = RelationshipGraph()
    g.remove_entity("does_not_exist")  # should not raise


def test_get_entity_type() -> None:
    g = RelationshipGraph()
    g.add_entity("unit_a", EntityType.UNIT)
    assert g.get_entity_type("unit_a") == EntityType.UNIT.value
    assert g.get_entity_type("missing") is None


# ---------------------------------------------------------------------------
# 4. RelationshipGraph: add_relationship, has_relationship, remove_relationship
# ---------------------------------------------------------------------------

def test_add_and_has_relationship() -> None:
    g = RelationshipGraph()
    g.add_entity("cmd", EntityType.COMMANDER)
    g.add_entity("unit", EntityType.UNIT)
    g.add_relationship("cmd", "unit", RelationType.COMMANDS)
    assert g.has_relationship("cmd", "unit")
    assert not g.has_relationship("unit", "cmd")


def test_remove_relationship() -> None:
    g = RelationshipGraph()
    g.add_entity("cmd", EntityType.COMMANDER)
    g.add_entity("unit", EntityType.UNIT)
    g.add_relationship("cmd", "unit", RelationType.COMMANDS)
    g.remove_relationship("cmd", "unit")
    assert not g.has_relationship("cmd", "unit")


def test_remove_nonexistent_relationship_no_error() -> None:
    g = RelationshipGraph()
    g.remove_relationship("a", "b")  # should not raise


# ---------------------------------------------------------------------------
# 5. RelationshipGraph: get_relationships_from/to with and without filter
# ---------------------------------------------------------------------------

def test_get_relationships_from_no_filter() -> None:
    g = make_graph()
    edges = g.get_relationships_from("blue_cmd")
    targets = {t for _, t, _ in edges}
    assert "blue_1bn" in targets
    assert "blue_2bn" in targets


def test_get_relationships_from_with_filter() -> None:
    g = make_graph()
    edges = g.get_relationships_from("blue_cmd", RelationType.COMMANDS)
    assert len(edges) == 2
    for _, _, data in edges:
        assert data["rel_type"] == RelationType.COMMANDS.value


def test_get_relationships_from_nonexistent_entity() -> None:
    g = RelationshipGraph()
    assert g.get_relationships_from("missing") == []


def test_get_relationships_to_no_filter() -> None:
    g = make_graph()
    edges = g.get_relationships_to("blue_1bn")
    sources = {s for s, _, _ in edges}
    assert "blue_cmd" in sources
    assert "msr_1" in sources


def test_get_relationships_to_with_filter() -> None:
    g = make_graph()
    edges = g.get_relationships_to("blue_1bn", RelationType.COMMANDS)
    assert len(edges) == 1
    assert edges[0][0] == "blue_cmd"


def test_get_relationships_to_nonexistent_entity() -> None:
    g = RelationshipGraph()
    assert g.get_relationships_to("missing") == []


# ---------------------------------------------------------------------------
# 6. RelationshipGraph: node_count, edge_count
# ---------------------------------------------------------------------------

def test_node_count() -> None:
    g = make_graph()
    assert g.node_count == 8


def test_edge_count() -> None:
    g = make_graph()
    # COMMANDS x2, BELONGS_TO x1, SUPPLIES x1, PASSES_THROUGH x1 = 5
    assert g.edge_count == 5


# ---------------------------------------------------------------------------
# 7. RelationshipGraph: to_dict/from_dict roundtrip
# ---------------------------------------------------------------------------

def test_to_dict_from_dict_roundtrip() -> None:
    g = make_graph()
    data = g.to_dict()

    assert "nodes" in data
    assert "edges" in data
    assert "blue_force" in data["nodes"]
    assert any(e["source"] == "blue_cmd" and e["target"] == "blue_1bn" for e in data["edges"])

    g2 = RelationshipGraph.from_dict(data)
    assert g2.node_count == g.node_count
    assert g2.edge_count == g.edge_count
    assert g2.has_entity("blue_force")
    assert g2.has_relationship("blue_cmd", "blue_1bn")
    assert g2.get_entity_type("blue_force") == EntityType.FORCE.value


# ---------------------------------------------------------------------------
# 8. RelationshipGraph: recalculate_adjacency
# ---------------------------------------------------------------------------

def test_recalculate_adjacency_friendly() -> None:
    g = RelationshipGraph()
    unit_a = make_unit("unit_a", Side.BLUE, 0, 0)
    unit_b = make_unit("unit_b", Side.BLUE, 1, 0)  # adjacent
    g.add_entity("unit_a", EntityType.UNIT)
    g.add_entity("unit_b", EntityType.UNIT)

    state = MockGameState({"unit_a": unit_a, "unit_b": unit_b})
    g.recalculate_adjacency(state)

    assert g.has_relationship("unit_a", "unit_b")
    assert g.has_relationship("unit_b", "unit_a")
    # Verify it's ADJACENT_TO, not THREATENS
    edges = g.get_relationships_from("unit_a", RelationType.ADJACENT_TO)
    assert len(edges) == 1


def test_recalculate_adjacency_enemy() -> None:
    g = RelationshipGraph()
    unit_a = make_unit("unit_a", Side.BLUE, 0, 0)
    unit_b = make_unit("unit_b", Side.RED, 1, 0)  # adjacent, enemy
    g.add_entity("unit_a", EntityType.UNIT)
    g.add_entity("unit_b", EntityType.UNIT)

    state = MockGameState({"unit_a": unit_a, "unit_b": unit_b})
    g.recalculate_adjacency(state)

    edges = g.get_relationships_from("unit_a", RelationType.THREATENS)
    assert len(edges) == 1
    assert edges[0][1] == "unit_b"


def test_recalculate_adjacency_far_units() -> None:
    g = RelationshipGraph()
    unit_a = make_unit("unit_a", Side.BLUE, 0, 0)
    unit_b = make_unit("unit_b", Side.BLUE, 5, 0)  # far away
    g.add_entity("unit_a", EntityType.UNIT)
    g.add_entity("unit_b", EntityType.UNIT)

    state = MockGameState({"unit_a": unit_a, "unit_b": unit_b})
    g.recalculate_adjacency(state)

    assert not g.has_relationship("unit_a", "unit_b")
    assert not g.has_relationship("unit_b", "unit_a")


def test_recalculate_adjacency_skips_destroyed() -> None:
    g = RelationshipGraph()
    unit_a = make_unit("unit_a", Side.BLUE, 0, 0)
    unit_b = Unit(
        id="unit_b", name="unit_b", side=Side.BLUE,
        unit_type=UnitType.INFANTRY, size=UnitSize.BATTALION,
        position=HexCoord(q=1, r=0), strength=0.0, morale=0.0,
        movement_points=0, max_movement_points=4,
        attack_power=1.0, defense_power=1.0, effective_range=2,
        ammo=0.0, fuel=0.0, status=UnitStatus.DESTROYED,
    )
    g.add_entity("unit_a", EntityType.UNIT)
    g.add_entity("unit_b", EntityType.UNIT)

    state = MockGameState({"unit_a": unit_a, "unit_b": unit_b})
    g.recalculate_adjacency(state)

    assert not g.has_relationship("unit_a", "unit_b")


# ---------------------------------------------------------------------------
# 9. RelationshipGraph: update_unit_position
# ---------------------------------------------------------------------------

def test_update_unit_position_removes_old_adds_new() -> None:
    g = RelationshipGraph()
    g.add_entity("unit_a", EntityType.UNIT)
    g.add_entity("hex_0_0", EntityType.TERRAIN_FEATURE)
    g.add_entity("hex_1_0", EntityType.TERRAIN_FEATURE)
    g.add_relationship("unit_a", "hex_0_0", RelationType.LOCATED_AT)

    g.update_unit_position("unit_a", "hex_0_0", "hex_1_0")

    assert not g.has_relationship("unit_a", "hex_0_0")
    assert g.has_relationship("unit_a", "hex_1_0")


def test_update_unit_position_new_hex_not_in_graph() -> None:
    g = RelationshipGraph()
    g.add_entity("unit_a", EntityType.UNIT)
    g.add_entity("hex_0_0", EntityType.TERRAIN_FEATURE)
    g.add_relationship("unit_a", "hex_0_0", RelationType.LOCATED_AT)

    # hex_1_0 not added to graph — should not add edge
    g.update_unit_position("unit_a", "hex_0_0", "hex_1_0")

    assert not g.has_relationship("unit_a", "hex_0_0")
    assert not g.has_relationship("unit_a", "hex_1_0")


# ---------------------------------------------------------------------------
# 10. GraphTools: query_supply_chain
# ---------------------------------------------------------------------------

def test_query_supply_chain_finds_route_and_choke_point() -> None:
    g = make_graph()
    tools = GraphTools(g)
    result = tools.query_supply_chain("blue_1bn")

    assert result["is_supplied"] is True
    assert "msr_1" in result["supply_path"]
    assert "bridge_alpha" in result["choke_points"]


def test_query_supply_chain_no_supply() -> None:
    g = make_graph()
    tools = GraphTools(g)
    result = tools.query_supply_chain("blue_2bn")

    assert result["is_supplied"] is False
    assert result["supply_path"] == []
    assert result["choke_points"] == []


def test_query_supply_chain_nonexistent_unit() -> None:
    g = make_graph()
    tools = GraphTools(g)
    result = tools.query_supply_chain("ghost_unit")

    assert result["is_supplied"] is False


# ---------------------------------------------------------------------------
# 11. GraphTools: query_affected_units (bridge destruction)
# ---------------------------------------------------------------------------

def test_query_affected_units_bridge_affects_supplied_unit() -> None:
    g = make_graph()
    tools = GraphTools(g)
    result = tools.query_affected_units("bridge_alpha")

    assert "blue_1bn" in result["affected_units"]
    assert result["impact"] == "supply_cut"


def test_query_affected_units_direct_supply_route() -> None:
    g = make_graph()
    tools = GraphTools(g)
    # Destroying the supply route directly
    result = tools.query_affected_units("msr_1")

    assert "blue_1bn" in result["affected_units"]
    assert result["impact"] == "supply_cut"


def test_query_affected_units_no_impact() -> None:
    g = make_graph()
    tools = GraphTools(g)
    # red_1bn has no supply connections
    result = tools.query_affected_units("red_1bn")

    assert result["affected_units"] == []
    assert result["impact"] == "none"


def test_query_affected_units_nonexistent_target() -> None:
    g = make_graph()
    tools = GraphTools(g)
    result = tools.query_affected_units("ghost")

    assert result["affected_units"] == []
    assert result["impact"] == "none"


# ---------------------------------------------------------------------------
# 12. GraphTools: query_command_chain
# ---------------------------------------------------------------------------

def test_query_command_chain_finds_commander_and_siblings() -> None:
    g = make_graph()
    tools = GraphTools(g)
    result = tools.query_command_chain("blue_1bn")

    assert "blue_cmd" in result["chain_of_command"]
    assert "blue_2bn" in result["sibling_units"]
    assert "blue_1bn" not in result["sibling_units"]


def test_query_command_chain_no_commander() -> None:
    g = make_graph()
    tools = GraphTools(g)
    result = tools.query_command_chain("red_1bn")

    assert result["chain_of_command"] == []
    assert result["sibling_units"] == []


# ---------------------------------------------------------------------------
# 13. GraphTools: query_nearby_units
# ---------------------------------------------------------------------------

def test_query_nearby_units_friendly_and_enemy() -> None:
    g = RelationshipGraph()
    g.add_entity("unit_a", EntityType.UNIT, {"side": "BLUE"})
    g.add_entity("unit_b", EntityType.UNIT, {"side": "BLUE"})
    g.add_entity("unit_c", EntityType.UNIT, {"side": "RED"})
    g.add_relationship("unit_a", "unit_b", RelationType.ADJACENT_TO)
    g.add_relationship("unit_a", "unit_c", RelationType.THREATENS)

    tools = GraphTools(g)
    result = tools.query_nearby_units("unit_a")

    assert "unit_b" in result["friendly"]
    assert "unit_c" in result["enemy"]


def test_query_nearby_units_friendly_only() -> None:
    g = RelationshipGraph()
    g.add_entity("unit_a", EntityType.UNIT, {"side": "BLUE"})
    g.add_entity("unit_b", EntityType.UNIT, {"side": "BLUE"})
    g.add_entity("unit_c", EntityType.UNIT, {"side": "RED"})
    g.add_relationship("unit_a", "unit_b", RelationType.ADJACENT_TO)
    g.add_relationship("unit_a", "unit_c", RelationType.THREATENS)

    tools = GraphTools(g)
    result = tools.query_nearby_units("unit_a", friendly_only=True)

    assert "unit_b" in result["friendly"]
    assert result["enemy"] == []


# ---------------------------------------------------------------------------
# 14. GraphTools: non-existent unit -> empty results
# ---------------------------------------------------------------------------

def test_all_queries_nonexistent_unit_return_empty() -> None:
    g = RelationshipGraph()
    tools = GraphTools(g)

    assert tools.query_supply_chain("x")["is_supplied"] is False
    assert tools.query_affected_units("x")["affected_units"] == []
    assert tools.query_command_chain("x")["chain_of_command"] == []
    assert tools.query_nearby_units("x")["friendly"] == []
    assert tools.query_fire_support("x")["available_support"] == []


# ---------------------------------------------------------------------------
# 15. GraphTools: get_tool_definitions -> returns 4 tools
# ---------------------------------------------------------------------------

def test_get_tool_definitions_returns_six_tools() -> None:
    g = RelationshipGraph()
    tools = GraphTools(g)
    definitions = tools.get_tool_definitions()

    assert len(definitions) == 6
    names = {d["function"]["name"] for d in definitions}
    assert names == {
        "query_supply_chain",
        "query_affected_units",
        "query_fire_support",
        "query_command_chain",
        "query_controlled_units",
        "query_command_scope",
    }


# ---------------------------------------------------------------------------
# 16. GraphTools: query_command_scope
# ---------------------------------------------------------------------------

def test_query_command_scope_returns_commanded_units() -> None:
    g = RelationshipGraph()
    g.add_entity("cmd_a", EntityType.COMMANDER, {"side": "BLUE"})
    g.add_entity("unit_x", EntityType.UNIT, {"side": "BLUE"})
    g.add_entity("unit_y", EntityType.UNIT, {"side": "BLUE"})
    g.add_relationship("cmd_a", "unit_x", RelationType.COMMANDS)
    g.add_relationship("cmd_a", "unit_y", RelationType.COMMANDS)

    tools = GraphTools(g)
    result = tools.query_command_scope("cmd_a")

    assert result["commander_id"] == "cmd_a"
    assert set(result["commanded_unit_ids"]) == {"unit_x", "unit_y"}


def test_query_command_scope_no_commands_returns_empty() -> None:
    g = RelationshipGraph()
    g.add_entity("cmd_b", EntityType.COMMANDER, {"side": "BLUE"})

    tools = GraphTools(g)
    result = tools.query_command_scope("cmd_b")

    assert result["commander_id"] == "cmd_b"
    assert result["commanded_unit_ids"] == []


def test_query_command_scope_nonexistent_commander_returns_empty() -> None:
    g = RelationshipGraph()
    tools = GraphTools(g)
    result = tools.query_command_scope("no_such_cmd")

    assert result["commander_id"] == "no_such_cmd"
    assert result["commanded_unit_ids"] == []


def test_query_command_scope_excludes_non_unit_targets() -> None:
    """COMMANDS edge pointing to a Force entity should not appear in commanded_unit_ids."""
    g = RelationshipGraph()
    g.add_entity("cmd_c", EntityType.COMMANDER, {"side": "BLUE"})
    g.add_entity("unit_z", EntityType.UNIT, {"side": "BLUE"})
    g.add_entity("blue_force", EntityType.FORCE, {"name": "Blue Force"})
    g.add_relationship("cmd_c", "unit_z", RelationType.COMMANDS)
    # Non-standard edge to a Force — should be filtered out
    g._graph.add_edge("cmd_c", "blue_force", rel_type="COMMANDS")

    tools = GraphTools(g)
    result = tools.query_command_scope("cmd_c")

    assert "unit_z" in result["commanded_unit_ids"]
    assert "blue_force" not in result["commanded_unit_ids"]


def test_get_tool_definitions_structure() -> None:
    g = RelationshipGraph()
    tools = GraphTools(g)
    for defn in tools.get_tool_definitions():
        assert defn["type"] == "function"
        assert "name" in defn["function"]
        assert "description" in defn["function"]
        assert "parameters" in defn["function"]
        assert defn["function"]["parameters"]["type"] == "object"
        assert "required" in defn["function"]["parameters"]
