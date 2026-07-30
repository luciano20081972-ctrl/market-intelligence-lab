# Infrastructure data classification

Classes are: public health metadata; source/CI metadata; identity data; workspace research data; licensed financial data; secrets; and scrubbed operational telemetry. Secrets, JWTs, password material, authorization headers, provider keys, complete request bodies, and brokerage data are prohibited from telemetry and the registry.

Identity and workspace data require authenticated least-privilege access. Financial payloads require a separate provider-license decision. Backups inherit the highest classification they contain and must be encrypted, access logged, retained deliberately, and exportable.
