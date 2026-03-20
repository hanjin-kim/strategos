from __future__ import annotations
import networkx as nx
from app.graph.military_ontology import EntityType, RelationType
from app.utils.hex_grid import hex_distance, hex_neighbors
from app.models.domain import HexCoord, UnitStatus


class RelationshipGraph:
    """NetworkX DiGraph wrapper for military entity relationships."""

    def __init__(self):
        self._graph = nx.DiGraph()

    # --- Build ---
    def add_entity(self, entity_id: str, entity_type: EntityType, attributes: dict | None = None) -> None:
        attrs = {"entity_type": entity_type.value}
        if attributes:
            attrs.update(attributes)
        self._graph.add_node(entity_id, **attrs)

    def add_relationship(self, source_id: str, target_id: str, rel_type: RelationType, attributes: dict | None = None) -> None:
        attrs = {"rel_type": rel_type.value}
        if attributes:
            attrs.update(attributes)
        self._graph.add_edge(source_id, target_id, **attrs)

    def remove_entity(self, entity_id: str) -> None:
        if self._graph.has_node(entity_id):
            self._graph.remove_node(entity_id)

    def remove_relationship(self, source_id: str, target_id: str) -> None:
        if self._graph.has_edge(source_id, target_id):
            self._graph.remove_edge(source_id, target_id)

    def has_entity(self, entity_id: str) -> bool:
        return self._graph.has_node(entity_id)

    def has_relationship(self, source_id: str, target_id: str) -> bool:
        return self._graph.has_edge(source_id, target_id)

    def get_entity_type(self, entity_id: str) -> str | None:
        if not self._graph.has_node(entity_id):
            return None
        return self._graph.nodes[entity_id].get("entity_type")

    def get_relationships_from(self, entity_id: str, rel_type: RelationType | None = None) -> list[tuple[str, str, dict]]:
        """Get all outgoing relationships. Optionally filter by type."""
        if not self._graph.has_node(entity_id):
            return []
        edges = []
        for _, target, data in self._graph.out_edges(entity_id, data=True):
            if rel_type is None or data.get("rel_type") == rel_type.value:
                edges.append((entity_id, target, data))
        return edges

    def get_relationships_to(self, entity_id: str, rel_type: RelationType | None = None) -> list[tuple[str, str, dict]]:
        """Get all incoming relationships."""
        if not self._graph.has_node(entity_id):
            return []
        edges = []
        for source, _, data in self._graph.in_edges(entity_id, data=True):
            if rel_type is None or data.get("rel_type") == rel_type.value:
                edges.append((source, entity_id, data))
        return edges

    # --- Runtime updates ---
    def update_unit_position(self, unit_id: str, old_hex_id: str, new_hex_id: str) -> None:
        """Update LOCATED_AT edge when unit moves."""
        self.remove_relationship(unit_id, old_hex_id)
        if self.has_entity(new_hex_id):
            self.add_relationship(unit_id, new_hex_id, RelationType.LOCATED_AT)

    def recalculate_adjacency(self, game_state) -> None:
        """Rebuild all ADJACENT_TO and THREATENS edges based on current positions."""
        # Remove existing ADJACENT_TO and THREATENS edges
        edges_to_remove = []
        for u, v, data in self._graph.edges(data=True):
            if data.get("rel_type") in (RelationType.ADJACENT_TO.value, RelationType.THREATENS.value):
                edges_to_remove.append((u, v))
        for u, v in edges_to_remove:
            self._graph.remove_edge(u, v)

        # Rebuild from game state
        units = [u for u in game_state.units.values() if u.status != UnitStatus.DESTROYED]
        for i, unit_a in enumerate(units):
            for unit_b in units[i + 1:]:
                dist = hex_distance(unit_a.position, unit_b.position)
                if dist <= 1:
                    if unit_a.side == unit_b.side:
                        self.add_relationship(unit_a.id, unit_b.id, RelationType.ADJACENT_TO)
                        self.add_relationship(unit_b.id, unit_a.id, RelationType.ADJACENT_TO)
                    else:
                        self.add_relationship(unit_a.id, unit_b.id, RelationType.THREATENS)
                        self.add_relationship(unit_b.id, unit_a.id, RelationType.THREATENS)

    # --- Scenario loading ---
    def load_from_scenario(self, scenario_data: dict, game_state) -> None:
        """Build graph from scenario JSON relationships section + game state."""
        # Add units as entities
        for uid, unit in game_state.units.items():
            self.add_entity(uid, EntityType.UNIT, {"side": unit.side.value, "type": unit.unit_type.value})

        # Add commanders
        for cid, cmd in game_state.commanders.items():
            self.add_entity(cid, EntityType.COMMANDER, {"side": cmd.side.value, "rank": cmd.rank})

        # Add forces
        for side, force in game_state.forces.items():
            self.add_entity(side.value, EntityType.FORCE, {"name": force.name})

        # Add relationships from scenario JSON
        for rel in scenario_data.get("relationships", []):
            source = rel["source"]
            target = rel["target"]
            rel_type = RelationType(rel["type"])
            self.add_relationship(source, target, rel_type)

        # Auto-generate initial adjacency
        self.recalculate_adjacency(game_state)

    # --- Serialization ---
    def to_dict(self) -> dict:
        nodes = {}
        for nid, data in self._graph.nodes(data=True):
            nodes[nid] = dict(data)
        edges = []
        for u, v, data in self._graph.edges(data=True):
            edges.append({"source": u, "target": v, **data})
        return {"nodes": nodes, "edges": edges}

    @classmethod
    def from_dict(cls, data: dict) -> RelationshipGraph:
        graph = cls()
        for nid, attrs in data.get("nodes", {}).items():
            graph._graph.add_node(nid, **attrs)
        for edge in data.get("edges", []):
            edge = dict(edge)
            source = edge.pop("source")
            target = edge.pop("target")
            graph._graph.add_edge(source, target, **edge)
        return graph

    @property
    def node_count(self) -> int:
        return self._graph.number_of_nodes()

    @property
    def edge_count(self) -> int:
        return self._graph.number_of_edges()
