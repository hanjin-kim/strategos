from __future__ import annotations
import networkx as nx
from app.graph.relationship_graph import RelationshipGraph
from app.graph.military_ontology import EntityType, RelationType


class GraphTools:
    """Graph query functions for agent tool calling."""

    def __init__(self, graph: RelationshipGraph):
        self.graph = graph

    def query_supply_chain(self, unit_id: str) -> dict:
        """Trace supply route to unit. Return path and choke points."""
        g = self.graph._graph
        if not g.has_node(unit_id):
            return {"supply_path": [], "choke_points": [], "is_supplied": False}

        # Find supply routes that supply this unit
        suppliers = []
        for source, _, data in g.in_edges(unit_id, data=True):
            if data.get("rel_type") == RelationType.SUPPLIES.value:
                suppliers.append(source)

        if not suppliers:
            return {"supply_path": [], "choke_points": [], "is_supplied": False}

        # Find terrain features the supply route passes through (choke points)
        choke_points = []
        for route_id in suppliers:
            for _, target, data in g.out_edges(route_id, data=True):
                if data.get("rel_type") == RelationType.PASSES_THROUGH.value:
                    choke_points.append(target)

        return {
            "supply_path": suppliers,
            "choke_points": choke_points,
            "is_supplied": True,
        }

    def query_affected_units(self, target_id: str) -> dict:
        """If target (bridge, HQ, supply route) is destroyed, which units are affected?"""
        g = self.graph._graph
        if not g.has_node(target_id):
            return {"affected_units": [], "impact": "none"}

        affected = set()

        # Direct: units supplied by this route, or supported by this installation
        for _, target, data in g.out_edges(target_id, data=True):
            if data.get("rel_type") in (RelationType.SUPPLIES.value, RelationType.SUPPORTS.value):
                if g.nodes[target].get("entity_type") == EntityType.UNIT.value:
                    affected.add(target)

        # Indirect: supply routes passing through this terrain feature
        for source, _, data in g.in_edges(target_id, data=True):
            if data.get("rel_type") == RelationType.PASSES_THROUGH.value:
                # This supply route passes through target; find units it supplies
                for _, supplied_unit, sdata in g.out_edges(source, data=True):
                    if sdata.get("rel_type") == RelationType.SUPPLIES.value:
                        affected.add(supplied_unit)

        return {
            "affected_units": list(affected),
            "impact": "supply_cut" if affected else "none",
        }

    def query_fire_support(self, unit_id: str, max_range_hexes: int = 3) -> dict:
        """Find artillery/support units within range."""
        g = self.graph._graph
        if not g.has_node(unit_id):
            return {"available_support": []}

        # Find friendly adjacent/nearby units via graph traversal
        supporters = []
        # Check ADJACENT_TO relationships up to max_range_hexes hops
        try:
            ego = nx.ego_graph(g, unit_id, radius=max_range_hexes, undirected=True)
            for node in ego.nodes():
                if node == unit_id:
                    continue
                node_data = g.nodes[node]
                if node_data.get("entity_type") == EntityType.UNIT.value:
                    if node_data.get("type") in ("ARTILLERY", "HQ"):
                        supporters.append(node)
        except nx.NetworkXError:
            pass

        return {"available_support": supporters}

    def query_command_chain(self, unit_id: str) -> dict:
        """Get command hierarchy (superiors) and sibling units."""
        g = self.graph._graph
        if not g.has_node(unit_id):
            return {"chain_of_command": [], "sibling_units": []}

        # Find commander (COMMANDS -> this unit)
        commanders = []
        for source, _, data in g.in_edges(unit_id, data=True):
            if data.get("rel_type") == RelationType.COMMANDS.value:
                commanders.append(source)

        # Find siblings (other units commanded by same commander)
        siblings = []
        for cmd_id in commanders:
            for _, target, data in g.out_edges(cmd_id, data=True):
                if data.get("rel_type") == RelationType.COMMANDS.value and target != unit_id:
                    siblings.append(target)

        return {
            "chain_of_command": commanders,
            "sibling_units": siblings,
        }

    def query_nearby_units(self, unit_id: str, friendly_only: bool = False) -> dict:
        """Get units connected via ADJACENT_TO or THREATENS."""
        g = self.graph._graph
        if not g.has_node(unit_id):
            return {"friendly": [], "enemy": []}

        friendly = []
        enemy = []

        for _, target, data in g.out_edges(unit_id, data=True):
            rel = data.get("rel_type")
            if rel == RelationType.ADJACENT_TO.value:
                friendly.append(target)
            elif rel == RelationType.THREATENS.value:
                enemy.append(target)

        if friendly_only:
            return {"friendly": friendly, "enemy": []}
        return {"friendly": friendly, "enemy": enemy}

    def get_tool_definitions(self) -> list[dict]:
        """Return OpenAI function calling format tool definitions."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "query_supply_chain",
                    "description": "Trace supply route to a unit. Returns supply path and choke points.",
                    "parameters": {
                        "type": "object",
                        "properties": {"unit_id": {"type": "string"}},
                        "required": ["unit_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "query_affected_units",
                    "description": "Find units affected if a target (bridge, HQ, route) is destroyed.",
                    "parameters": {
                        "type": "object",
                        "properties": {"target_id": {"type": "string"}},
                        "required": ["target_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "query_fire_support",
                    "description": "Find artillery and support assets within range of a unit.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "unit_id": {"type": "string"},
                            "max_range_hexes": {"type": "integer", "default": 3},
                        },
                        "required": ["unit_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "query_command_chain",
                    "description": "Get command hierarchy and sibling units.",
                    "parameters": {
                        "type": "object",
                        "properties": {"unit_id": {"type": "string"}},
                        "required": ["unit_id"],
                    },
                },
            },
        ]
