import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api";
import { CompanyPicker } from "../components/CompanyPicker";
import { EmptyState, ErrorState, LoadingState } from "../components/States";

export function CompanyDriverProfile() {
  const companies = useQuery({ queryKey: ["economic-companies"], queryFn: () => api.economicEntities("Company") });
  const [companyId, setCompanyId] = useState("");
  const selectedCompanyId = companyId || companies.data?.items[0]?.id || "";
  const profile = useQuery({
    queryKey: ["driver-profile", selectedCompanyId], queryFn: () => api.companyDriverProfile(selectedCompanyId), enabled: Boolean(selectedCompanyId),
  });
  if (companies.isLoading) return <LoadingState label="Loading reference companies" />;
  if (companies.error) return <ErrorState error={companies.error} />;
  if (!companies.data?.items.length) return <EmptyState title="No profiles" detail="No reference companies are available." />;
  return <section><div className="page-heading"><div><p className="eyebrow">COMPANY-SPECIFIC INTELLIGENCE</p>
    <h1>Company Driver Profile</h1><p>Potential drivers, not trading signals or claims of causality.</p></div>
    <CompanyPicker companies={companies.data.items} value={selectedCompanyId} onChange={setCompanyId} /></div>
    {profile.isLoading ? <LoadingState label="Loading driver profile" /> : null}
    {profile.error ? <ErrorState error={profile.error} /> : null}
    {profile.data ? <><p className="callout"><strong>Scientific label:</strong> {profile.data.scientific_label}</p>
      <div className="source-grid">{profile.data.entries.map((entry) => <article className="panel" key={entry.id}>
        <p className="eyebrow">{entry.driver_category.replaceAll("_", " ")}</p>
        <h2>{Math.round(Number(entry.effective_relevance) * 100)}% relevance</h2>
        <p>{entry.explanation}</p><dl className="detail-list">
          <div><dt>Confidence</dt><dd>{Math.round(Number(entry.confidence) * 100)}%</dd></div>
          <div><dt>Evidence paths</dt><dd>{entry.supporting_relationship_ids.length}</dd></div>
          <div><dt>Source coverage</dt><dd>{entry.linked_entity_ids.length} linked entities</dd></div>
        </dl>
      </article>)}</div></> : null}
  </section>;
}
