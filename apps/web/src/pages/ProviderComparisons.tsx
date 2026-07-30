import { useQuery } from "@tanstack/react-query";
import { api } from "../api";

export function ProviderComparisons() {
  const query = useQuery({ queryKey: ["provider-comparisons"], queryFn: api.providerComparisons });
  return <section><h1>Provider comparisons</h1><p>Conflicts remain unresolved until an explicit decision is recorded. Values are never silently replaced.</p>
    {query.data?.items.map((comparison) => <article className="card" key={comparison.id}><h2>{comparison.resolution_status}</h2><p>{comparison.disagreements.length} disagreement(s) · {comparison.compared_at}</p><pre>{JSON.stringify(comparison.summary, null, 2)}</pre></article>)}</section>;
}
