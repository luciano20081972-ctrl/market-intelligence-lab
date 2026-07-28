import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import { EmptyState, ErrorState, LoadingState } from "../components/States";

export function DataSources() {
  const query = useQuery({ queryKey: ["sources"], queryFn: api.dataSources });
  if (query.isLoading) return <LoadingState label="Loading providers" />;
  if (query.error) return <ErrorState error={query.error} />;
  return <section><div className="page-heading"><div><p className="eyebrow">DATA GOVERNANCE</p><h1>Data sources</h1><p>Inspect provider health, record counts, freshness, and usage notes.</p></div></div>
    {query.data!.length === 0 ? <EmptyState title="No data providers" detail="Configure and run a provider before researching prices." /> : <div className="source-grid">{query.data!.map(source => <article className="panel" key={source.id}><div className="panel-title"><div><p className="eyebrow">{source.provider_type}</p><h2>{source.name}</h2></div><span className="health"><i />{source.health}</span></div><dl className="detail-list"><div><dt>Enabled</dt><dd>{source.is_enabled ? "Yes" : "No"}</dd></div><div><dt>Stored records</dt><dd>{source.stored_records.toLocaleString()}</dd></div><div><dt>Last retrieval</dt><dd>{source.last_successful_retrieval ? new Date(source.last_successful_retrieval).toLocaleString() : "Never"}</dd></div><div><dt>Freshness</dt><dd>{source.freshness_status}</dd></div></dl><p className="license-note">{source.license_notes}</p></article>)}</div>}
  </section>;
}
