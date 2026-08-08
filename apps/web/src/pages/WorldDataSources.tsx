import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { api } from "../api";
import { ErrorState, LoadingState } from "../components/States";

export function WorldDataSources() {
  const query = useQuery({ queryKey: ["world-data-sources"], queryFn: api.worldDataSources });
  if (query.isLoading) return <LoadingState label="Loading world data registry" />;
  if (query.error) return <ErrorState error={query.error} />;
  return <section><div className="page-heading"><div><p className="eyebrow">TEMPORAL TRUTH</p>
    <h1>World data sources</h1><p>Official datasets with explicit licenses, freshness, and simulation eligibility.</p></div></div>
    <div className="source-grid">{query.data!.map(source => <article className="panel" key={source.id}>
      <p className="eyebrow">{source.provider} · {source.transport}</p><h2>{source.title}</h2>
      <p><span className="version-chip">{source.temporal_mode}</span> <span className="version-chip">fixture verified</span></p>
      <dl className="detail-list"><div><dt>Frequency</dt><dd>{source.expected_frequency}</dd></div>
        <div><dt>License</dt><dd>{source.license}</dd></div></dl>
      <Link to={`/world-data/sources/${encodeURIComponent(source.id)}`}>Inspect source</Link>
    </article>)}</div></section>;
}
