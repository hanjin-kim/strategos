from __future__ import annotations
from app.domains.business.models import BusinessUnit, MarketNode


class BusinessState:
    """Business domain state. No hex grid, no military concepts."""

    def __init__(self, scenario_data: dict | None = None):
        self.turn: int = 0
        self.phase: str = "COMMAND"
        self.units: dict[str, BusinessUnit] = {}
        self.market_map: dict[str, dict] = {}  # "region:segment" -> market info
        self.commanders: dict[str, dict] = {}   # commander_id -> commander dict
        self.forces: dict[str, dict] = {}       # side -> force info
        if scenario_data:
            self._load_scenario(scenario_data)

    def get_unit(self, unit_id: str) -> BusinessUnit | None:
        return self.units.get(unit_id)

    def get_entity(self, entity_id: str) -> BusinessUnit | None:
        return self.get_unit(entity_id)

    def get_units_by_side(self, side: str) -> list[BusinessUnit]:
        return [u for u in self.units.values() if u.side == side]

    def get_entities_by_side(self, side: str) -> list[BusinessUnit]:
        return self.get_units_by_side(side)

    def get_competitors(self, unit_id: str) -> list[BusinessUnit]:
        """Get competitor units in the same market segment."""
        unit = self.units.get(unit_id)
        if not unit:
            return []
        return [
            u for u in self.units.values()
            if u.side != unit.side
            and u.position == unit.position
            and u.status != "BANKRUPT"
        ]

    def get_adjacent_competitors(self, unit_id: str) -> list[BusinessUnit]:
        """Get competitors in same or connected markets."""
        unit = self.units.get(unit_id)
        if not unit:
            return []
        key = f"{unit.position.region}:{unit.position.segment}"
        connected = self.market_map.get(key, {}).get("connections", [])
        valid_positions: set[MarketNode] = {unit.position}
        for conn in connected:
            parts = conn.split(":")
            if len(parts) == 2:
                valid_positions.add(MarketNode(region=parts[0], segment=parts[1]))
        return [
            u for u in self.units.values()
            if u.side != unit.side
            and u.position in valid_positions
            and u.status != "BANKRUPT"
        ]

    def update_unit(self, unit_id: str, **changes) -> None:
        """Update a business unit (creates new frozen instance)."""
        old = self.units[unit_id]
        self.units[unit_id] = old.model_copy(update=changes)

    def advance_turn(self) -> None:
        self.turn += 1
        self.phase = "COMMAND"

    def advance_phase(self) -> None:
        phases = ["COMMAND", "EXECUTION", "RESOLUTION"]
        idx = phases.index(self.phase)
        if idx < len(phases) - 1:
            self.phase = phases[idx + 1]

    def to_snapshot(self) -> dict:
        return {
            "turn": self.turn,
            "phase": self.phase,
            "units": {uid: u.model_dump() for uid, u in self.units.items()},
            "market_map": self.market_map,
            "commanders": self.commanders,
            "forces": self.forces,
        }

    def _load_scenario(self, data: dict) -> None:
        """Load business scenario JSON into state."""
        # Load market map
        for market in data.get("markets", []):
            key = f"{market['region']}:{market['segment']}"
            self.market_map[key] = market

        # Load forces, units, commanders
        for side_name, force_data in data.get("forces", {}).items():
            self.forces[side_name] = {
                "name": force_data.get("name", side_name),
                "side": side_name,
            }

            for unit_data in force_data.get("units", []):
                pos = unit_data.get("position", {})
                unit = BusinessUnit(
                    id=unit_data["id"],
                    name=unit_data["name"],
                    side=side_name,
                    status=unit_data.get("status", "ACTIVE"),
                    position=MarketNode(
                        region=pos.get("region", "unknown"),
                        segment=pos.get("segment", "unknown"),
                    ),
                    market_share=unit_data.get("market_share", 0.5),
                    revenue=unit_data.get("revenue", 1.0),
                    competitive_power=unit_data.get("competitive_power", 10.0),
                    brand_loyalty=unit_data.get("brand_loyalty", 10.0),
                    marketing_budget=unit_data.get("marketing_budget", 1.0),
                    cash_reserves=unit_data.get("cash_reserves", 1.0),
                    org_health=unit_data.get("org_health", 0.8),
                    rd_capability=unit_data.get("rd_capability", 0.5),
                )
                self.units[unit.id] = unit

            for cmd_data in force_data.get("commanders", []):
                self.commanders[cmd_data["id"]] = {
                    "id": cmd_data["id"],
                    "name": cmd_data["name"],
                    "side": side_name,
                    "rank": cmd_data.get("rank", "Manager"),
                    "unit_id": cmd_data.get("unit_id", ""),
                    "personality_traits": cmd_data.get("personality_traits", {}),
                }
