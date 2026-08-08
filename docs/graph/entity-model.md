# Economic entity model

v0.8 stores the economic graph in PostgreSQL adjacency tables. `economic_entities` is the canonical node table; `economic_relationships` connects nodes with ordinary foreign keys. Workspace scope, transactions, Temporal Truth, provenance, and authorization therefore remain in the existing database boundary.

Supported entity types are Company, Security, Subsidiary, BusinessSegment, Product, Facility, Supplier, Customer, Competitor, Commodity, Technology, Country, Region, Port, TransportationNode, EnergyMarket, GovernmentAgency, Regulation, EconomicSeries, ResearchTopic, Industry, and Event. The type column is extensible, but the application validates accepted values.

Every entity has an internal UUID, canonical and normalized names, lifecycle status, validity interval, first-seen and last-verified clocks, all seven Temporal Truth clocks, confidence, provenance metadata, aliases, and versioned external identifiers. UUIDs—not tickers or provider IDs—are stable graph identity.

Relationships support OWNS, OPERATES, HAS_SEGMENT, PRODUCES, USES, SUPPLIES, BUYS_FROM, SELLS_TO, COMPETES_WITH, LOCATED_IN, EXPOSED_TO, DEPENDS_ON, REGULATED_BY, CONSUMES, SHIPS_THROUGH, USES_TECHNOLOGY, AFFECTED_BY, HAS_SECURITY, and TRACKED_BY_SERIES. Candidate, verified, disputed, expired, and rejected states preserve uncertainty instead of erasing it.

PostgreSQL is adequate for the beta workload because the graph uses bounded 1–3 hop neighborhood reads, indexed inbound/outbound adjacency, recursive CTEs, and relational joins to evidence. A dedicated graph database is not justified by the v0.8 measurements. NetworkX and pgvector are not production dependencies; they remain optional future evaluation tools.
