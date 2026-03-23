from __future__ import annotations
from pydantic import BaseModel


class MarketNode(BaseModel, frozen=True):
    """A market segment node (replaces HexCoord)."""
    region: str      # "Korea", "China", "USA", "Europe"
    segment: str     # "EV", "ESS", "SmallBattery"

    def __hash__(self):
        return hash((self.region, self.segment))

    def __eq__(self, other):
        if not isinstance(other, MarketNode):
            return NotImplemented
        return self.region == other.region and self.segment == other.segment


class BusinessUnit(BaseModel, frozen=True):
    """A business unit entity."""
    id: str
    name: str
    side: str               # company name
    status: str = "ACTIVE"  # ACTIVE, STRUGGLING, BANKRUPT
    position: MarketNode    # which market it operates in
    market_share: float     # 0.0~1.0
    revenue: float          # relative revenue
    competitive_power: float  # pricing + product + distribution
    brand_loyalty: float    # defensive moat
    marketing_budget: float  # 0.0~1.0 (depletes with campaigns)
    cash_reserves: float    # 0.0~1.0 (depletes with expansion)
    org_health: float       # 0.0~1.0 (employee morale)
    rd_capability: float    # 0.0~1.0 (innovation strength)


class BusinessAction(BaseModel, frozen=True):
    """A business decision action."""
    action_id: str
    turn: int
    commander_id: str
    entity_id: str          # business unit id
    action_type: str        # EXPAND, COMPETE, DEFEND, RETREAT, INVEST_RD, HOLD
    target: MarketNode | None = None
    target_competitor_id: str | None = None
    intensity: float = 0.5  # 0.0~1.0 how aggressive
    reasoning: str = ""


class MarketTerrain(BaseModel, frozen=True):
    """Market characteristics of a node."""
    node: MarketNode
    market_size: float       # relative market size
    entry_barrier: float     # 0.0~1.0 (regulation, capital requirements)
    growth_rate: float       # annual growth rate
    volatility: float        # 0.0~1.0 (market stability)


class CompetitionOutcome(BaseModel, frozen=True):
    """Result of market competition between two business units."""
    attacker_id: str
    defender_id: str
    market_node: MarketNode
    attacker_share_change: float  # positive = gained share
    defender_share_change: float  # negative = lost share
    narrative: str = ""
