import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import { EmptyState, ErrorState, LoadingState } from "../components/States";

export function EnergyExplorer() {
  const query = useQuery({ queryKey: ["energy-series"], queryFn: api.energySeries });
  if (query.isLoading) return <LoadingState label="Loading EIA pilot" />;
  if (query.error) return <ErrorState error={query.error} />;
  return <section><div className="page-heading"><div><p className="eyebrow">EIA PILOT</p><h1>Retail electricity prices</h1>
    <p>A narrow monthly, geography-aware official dataset. Stale and ambiguous observations are visibly flagged.</p></div></div>
    {query.data!.total === 0 ? <EmptyState title="No EIA observations" detail="Live access is opt-in; fixture behavior is verified." /> :
      query.data!.items.map(series => <article className="panel" key={series.id}><h2>{series.title}</h2><p>{series.geography} · {series.units}</p></article>)}</section>;
}
