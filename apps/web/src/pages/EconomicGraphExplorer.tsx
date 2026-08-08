import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api";
import { CompanyPicker } from "../components/CompanyPicker";
import { EmptyState, ErrorState, LoadingState } from "../components/States";

export function EconomicGraphExplorer() {
  const companies = useQuery({ queryKey: ["economic-companies"], queryFn: () => api.economicEntities("Company") });
  const [companyId, setCompanyId] = useState("");
  const selectedCompanyId = companyId || companies.data?.items[0]?.id || "";
  const graph = useQuery({
    queryKey: ["economic-graph", selectedCompanyId], queryFn: () => api.economicGraph(selectedCompanyId), enabled: Boolean(selectedCompanyId),
  });
  if (companies.isLoading) return <LoadingState label="Loading economic entities" />;
  if (companies.error) return <ErrorState error={companies.error} />;
  if (!companies.data?.items.length) return <EmptyState title="No company entities" detail="Seed the reference graph first." />;
  return <section><div className="page-heading"><div><p className="eyebrow">ECONOMIC DRIVER GRAPH</p>
    <h1>Economic Graph Explorer</h1><p>Bounded three-hop view with cycle prevention and Temporal Truth.</p></div>
    <CompanyPicker companies={companies.data.items} value={selectedCompanyId} onChange={setCompanyId} /></div>
    {graph.isLoading ? <LoadingState label="Traversing bounded graph" /> : null}
    {graph.error ? <ErrorState error={graph.error} /> : null}
    {graph.data ? <><div className="metric-grid">
      <article className="panel"><p className="eyebrow">VISIBLE NODES</p><h2>{graph.data.nodes.length}</h2></article>
      <article className="panel"><p className="eyebrow">RELATIONSHIPS</p><h2>{graph.data.relationships.length}</h2></article>
      <article className="panel"><p className="eyebrow">QUERY LIMIT</p><h2>{graph.data.max_nodes}</h2><p>Maximum {graph.data.max_depth} hops</p></article>
    </div><div className="source-grid">{graph.data.nodes.map((node) => <article className="panel" key={node.id}>
      <p className="eyebrow">{node.entity_type}</p><h2>{node.canonical_name}</h2>
      <p><span className="version-chip">{node.status}</span> {Math.round(Number(node.confidence) * 100)}% confidence</p>
    </article>)}</div><section className="panel"><h2>Evidence-backed paths</h2>
      <ol>{graph.data.path_explanations.map((path) => <li key={path.relationship_ids.join("-")}>
        {path.depth} hop{path.depth === 1 ? "" : "s"} · {path.relationship_ids.length} relationship{path.relationship_ids.length === 1 ? "" : "s"}
      </li>)}</ol></section></> : null}
  </section>;
}
