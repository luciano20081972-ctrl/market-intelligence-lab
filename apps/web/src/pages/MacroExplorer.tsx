import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import { EmptyState, ErrorState, LoadingState } from "../components/States";

export function MacroExplorer() {
  const query = useQuery({ queryKey: ["macro-series"], queryFn: api.macroSeries });
  if (query.isLoading) return <LoadingState label="Loading macro series" />;
  if (query.error) return <ErrorState error={query.error} />;
  return <section><div className="page-heading"><div><p className="eyebrow">FRED · ALFRED</p><h1>Macro & vintage explorer</h1>
    <p>Latest-revised values are labelled; point-in-time research uses only simulation-eligible vintages.</p></div></div>
    <p><span className="version-chip">latest revised</span> <span className="version-chip">PIT safe</span> <span className="version-chip">temporal ambiguity flagged</span></p>
    {query.data!.total === 0 ? <EmptyState title="No macro series" detail="Configure a key and run an opt-in import, or use fixtures in tests." /> :
      query.data!.items.map(series => <article className="panel" key={series.id}><h2>{series.external_id} · {series.title}</h2><p>{series.units} · {series.frequency}</p></article>)}</section>;
}
