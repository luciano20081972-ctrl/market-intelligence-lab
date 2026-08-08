from __future__ import annotations

from enum import StrEnum


class EntityType(StrEnum):
    COMPANY = "Company"
    SECURITY = "Security"
    SUBSIDIARY = "Subsidiary"
    BUSINESS_SEGMENT = "BusinessSegment"
    PRODUCT = "Product"
    FACILITY = "Facility"
    SUPPLIER = "Supplier"
    CUSTOMER = "Customer"
    COMPETITOR = "Competitor"
    COMMODITY = "Commodity"
    TECHNOLOGY = "Technology"
    COUNTRY = "Country"
    REGION = "Region"
    PORT = "Port"
    TRANSPORTATION_NODE = "TransportationNode"
    ENERGY_MARKET = "EnergyMarket"
    GOVERNMENT_AGENCY = "GovernmentAgency"
    REGULATION = "Regulation"
    ECONOMIC_SERIES = "EconomicSeries"
    RESEARCH_TOPIC = "ResearchTopic"
    INDUSTRY = "Industry"
    EVENT = "Event"


class RelationshipType(StrEnum):
    OWNS = "OWNS"
    OPERATES = "OPERATES"
    HAS_SECURITY = "HAS_SECURITY"
    HAS_SEGMENT = "HAS_SEGMENT"
    PRODUCES = "PRODUCES"
    USES = "USES"
    SUPPLIES = "SUPPLIES"
    BUYS_FROM = "BUYS_FROM"
    SELLS_TO = "SELLS_TO"
    COMPETES_WITH = "COMPETES_WITH"
    LOCATED_IN = "LOCATED_IN"
    EXPOSED_TO = "EXPOSED_TO"
    DEPENDS_ON = "DEPENDS_ON"
    REGULATED_BY = "REGULATED_BY"
    CONSUMES = "CONSUMES"
    SHIPS_THROUGH = "SHIPS_THROUGH"
    USES_TECHNOLOGY = "USES_TECHNOLOGY"
    AFFECTED_BY = "AFFECTED_BY"
    TRACKED_BY_SERIES = "TRACKED_BY_SERIES"


ENTITY_TYPES = tuple(item.value for item in EntityType)
RELATIONSHIP_TYPES = tuple(item.value for item in RelationshipType)

DRIVER_CATEGORIES = (
    "financial",
    "macro",
    "industry",
    "commodity",
    "energy",
    "supply_chain",
    "technology",
    "regulatory",
    "geopolitical",
    "geospatial",
    "weather_environmental",
    "labor",
    "consumer",
    "scientific",
    "transportation",
    "agriculture",
    "water",
)
