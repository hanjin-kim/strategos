from __future__ import annotations
from app.models.domain import UnitType, UnitSize, Side


# APP-6 style symbol codes (simplified for frontend rendering)
UNIT_TYPE_SYMBOLS: dict[UnitType, str] = {
    UnitType.INFANTRY: "infantry",
    UnitType.MECHANIZED: "mechanized",
    UnitType.ARMOR: "armor",
    UnitType.ARTILLERY: "artillery",
    UnitType.AIR_DEFENSE: "air_defense",
    UnitType.ENGINEER: "engineer",
    UnitType.HQ: "headquarters",
}

SIZE_INDICATORS: dict[UnitSize, str] = {
    UnitSize.BATTALION: "III",    # 3 vertical lines
    UnitSize.BRIGADE: "X",       # 1 X
    UnitSize.DIVISION: "XX",     # 2 X's
}

SIDE_COLORS: dict[Side, dict[str, str]] = {
    Side.BLUE: {"fill": "#1e40af", "stroke": "#3b82f6", "text": "#ffffff"},
    Side.RED: {"fill": "#991b1b", "stroke": "#ef4444", "text": "#ffffff"},
}


def get_symbol_code(unit_type: UnitType, size: UnitSize, side: Side) -> dict:
    """Return symbol rendering data for frontend."""
    return {
        "type_symbol": UNIT_TYPE_SYMBOLS.get(unit_type, "unknown"),
        "size_indicator": SIZE_INDICATORS.get(size, ""),
        "colors": SIDE_COLORS.get(side, SIDE_COLORS[Side.BLUE]),
        "unit_type": unit_type.value,
        "unit_size": size.value,
        "side": side.value,
    }


def get_unit_display_info(unit) -> dict:
    """Get complete display info for a unit (for API responses)."""
    symbol = get_symbol_code(unit.unit_type, unit.size, unit.side)
    return {
        "id": unit.id,
        "name": unit.name,
        "symbol": symbol,
        "position": {"q": unit.position.q, "r": unit.position.r},
        "strength": unit.strength,
        "morale": unit.morale,
        "status": unit.status.value,
    }
