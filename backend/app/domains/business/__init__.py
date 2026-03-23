from app.core.domain_registry import register
from app.domains.business.factory import BusinessDomainFactory

register("business", BusinessDomainFactory())
