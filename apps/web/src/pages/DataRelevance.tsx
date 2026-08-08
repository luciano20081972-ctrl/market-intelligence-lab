import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api";
import { CompanyPicker } from "../components/CompanyPicker";
import { EmptyState, ErrorState, LoadingState } from "../components/States";

export function DataRelevance() {
  const companies = useQuery({ queryKey: ["economic-companies"], queryFn: () => api.economicEntities("Company") });
  const [companyId, setCompanyId] = useState("");
  const selectedCompanyId = companyId || companies.data?.items[0]?.id || "";
  const relevance = useQuery({
    queryKey: ["data-relevance", selectedCompanyId], queryFn: () => api.dataRelevance(selectedCompanyId), enabled: Boolean(selectedCompanyId),
  });
  if (companies.isLoading) return <LoadingState label="Loading reference companies" />;
  if (companies.error) return <ErrorState error={companies.error} />;
  if (!companies.data?.items.length) return <EmptyState title="No routing decisions" detail="No reference companies are available." />;
  return <section><div className="page-heading"><div><p className="eyebrow">DETERMINISTIC ROUTER</p>
    <h1>Data Relevance</h1><p>Process only datasets supported by company-specific drivers and paths.</p></div>
    <CompanyPicker companies={companies.data.items} value={selectedCompanyId} onChange={setCompanyId} /></div>
    {relevance.isLoading ? <LoadingState label="Loading relevance decisions" /> : null}
    {relevance.error ? <ErrorState error={relevance.error} /> : null}
    {relevance.data ? <div className="table-wrap"><table><thead><tr>
      <th>Dataset</th><th>Decision</th><th>Relevance</th><th>Confidence</th><th>Reason codes</th><th>Paths</th>
    </tr></thead><tbody>{relevance.data.items.map((item) => <tr key={item.id}>
      <td>{item.dataset_id}</td><td><span className="version-chip">{item.decision}</span></td>
      <td>{Math.round(Number(item.relevance_score) * 100)}%</td>
      <td>{Math.round(Number(item.confidence) * 100)}%</td><td>{item.reason_codes.join(", ")}</td>
      <td>{item.supporting_graph_paths.length}</td>
    </tr>)}</tbody></table></div> : null}
  </section>;
}
