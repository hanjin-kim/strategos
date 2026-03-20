from __future__ import annotations
from enum import Enum


class EntityType(str, Enum):
    FORCE = "Force"
    UNIT = "Unit"
    COMMANDER = "Commander"
    WEAPON_SYSTEM = "WeaponSystem"
    INSTALLATION = "Installation"
    TERRAIN_FEATURE = "TerrainFeature"
    SUPPLY_ROUTE = "SupplyRoute"
    AIR_ASSET = "AirAsset"


class RelationType(str, Enum):
    COMMANDS = "COMMANDS"
    BELONGS_TO = "BELONGS_TO"
    EQUIPPED_WITH = "EQUIPPED_WITH"
    LOCATED_AT = "LOCATED_AT"
    ADJACENT_TO = "ADJACENT_TO"
    SUPPLIES = "SUPPLIES"
    PASSES_THROUGH = "PASSES_THROUGH"
    SUPPORTS = "SUPPORTS"
    THREATENS = "THREATENS"
    PROTECTS = "PROTECTS"
    COVERS = "COVERS"


# Source/target type constraints for each relation
RELATION_CONSTRAINTS: dict[RelationType, tuple[set[EntityType], set[EntityType]]] = {
    RelationType.COMMANDS: ({EntityType.COMMANDER}, {EntityType.UNIT}),
    RelationType.BELONGS_TO: ({EntityType.UNIT}, {EntityType.FORCE}),
    RelationType.EQUIPPED_WITH: ({EntityType.UNIT}, {EntityType.WEAPON_SYSTEM}),
    RelationType.LOCATED_AT: ({EntityType.UNIT}, {EntityType.TERRAIN_FEATURE}),
    RelationType.ADJACENT_TO: ({EntityType.UNIT}, {EntityType.UNIT}),
    RelationType.SUPPLIES: ({EntityType.SUPPLY_ROUTE}, {EntityType.UNIT}),
    RelationType.PASSES_THROUGH: ({EntityType.SUPPLY_ROUTE}, {EntityType.TERRAIN_FEATURE}),
    RelationType.SUPPORTS: ({EntityType.INSTALLATION}, {EntityType.UNIT}),
    RelationType.THREATENS: ({EntityType.UNIT}, {EntityType.UNIT}),
    RelationType.PROTECTS: ({EntityType.UNIT}, {EntityType.INSTALLATION}),
    RelationType.COVERS: ({EntityType.AIR_ASSET}, {EntityType.TERRAIN_FEATURE}),
}
