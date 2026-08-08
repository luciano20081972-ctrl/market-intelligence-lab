import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api";
import { CompanyPicker } from "../components/CompanyPicker";
import { RelationshipEvidencePanel } from "../components/RelationshipEvidencePanel";
import { EmptyState, ErrorState, LoadingState } from "../components/States";

export function RelationshipEvidence() {
  const companies = useQuery({ queryKey: ["economic-companies"], queryFn: () => api.economicEntities("Company") });
  const [companyId, setCompanyId] = useState("");
  const selectedCompanyId = companyId || companies.data?.items[0]?.id || "";
  if (companies.isLoading) return <LoadingState label="Loading reference companies" />;
  if (companies.error) return <ErrorState error={companies.error} />;
  if (!companies.data?.items.length) return <EmptyState title="No evidence" detail="No graph companies are available." />;
  return <section><div className="page-heading"><div><p className="eyebrow">PROVENANCE</p>
    <h1>Relationship Evidence</h1><p>Source records and Temporal Truth behind graph relationships.</p></div>
    <CompanyPicker companies={companies.data.items} value={selectedCompanyId} onChange={setCompanyId} /></div>
    {selectedCompanyId ? <RelationshipEvidencePanel entityId={selectedCompanyId} /> : null}
  </section>;
}
