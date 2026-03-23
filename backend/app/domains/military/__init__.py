from app.core.domain_registry import register
from app.domains.military.factory import MilitaryDomainFactory

register("military", MilitaryDomainFactory())
