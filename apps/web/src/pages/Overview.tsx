import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { api } from "../api";
import { ErrorState, LoadingState } from "../components/States";

export function Overview() {
  const info = useQuery({ queryKey: ["system-info"], queryFn: api.systemInfo });
  const health = useQuery({ queryKey: ["health"], queryFn: api.health });
  const sources = useQuery({ queryKey: ["sources"], queryFn: api.dataSources });
  if (info.isLoading || health.isLoading || sources.isLoading) return <LoadingState label="Loading market overview" />;
  const error = info.error || health.error || sources.error;
  if (error) return <ErrorState error={error} />;
  const cards = [
    ["Tracked assets", info.data!.tracked_assets], ["Watchlists", info.data!.watchlists],
    ["Demonstration bars", info.data!.demonstration_bars.toLocaleString()], ["Data providers", sources.data!.length],
  ];
  return <section>
    <div className="page-heading"><div><p className="eyebrow">COMMAND CENTER</p><h1>Market overview</h1><p>A transparent foundation for research, provenance, and simulation.</p></div><Link className="button" to="/assets">Explore assets</Link></div>
    <div className="metric-grid">{cards.map(([label, value]) => <article className="metric" key={label}><span>{label}</span><strong>{value}</strong></article>)}</div>
    <div className="panel-grid">
      <article className="panel"><div className="panel-title"><div><p className="eyebrow">SYSTEM</p><h2>Environment health</h2></div><span className="health"><i />{health.data!.status}</span></div>
        <dl className="detail-list"><div><dt>Application</dt><dd>v{info.data!.version}</dd></div><div><dt>API</dt><dd>{health.data!.status}</dd></div><div><dt>Database</dt><dd>{info.data!.database_health} · {info.data!.database_engine}</dd></div><div><dt>Environment</dt><dd>{info.data!.environment}</dd></div></dl>
      </article>
      <article className="panel"><div className="panel-title"><div><p className="eyebrow">PROVENANCE</p><h2>Data-source status</h2></div></div>
        {sources.data!.map(source => <div className="source-row" key={source.id}><div><b>{source.name}</b><small>{source.provider_type} · {source.stored_records.toLocaleString()} records</small></div><span className="health"><i />{source.health}</span></div>)}
      </article>
    </div>
  </section>;
}
