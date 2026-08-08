import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import { EmptyState, ErrorState, LoadingState } from "./States";

export function RelationshipEvidencePanel({ entityId }: { entityId: string }) {
  const query = useQuery({
    queryKey: ["relationship-evidence", entityId],
    queryFn: () => api.relationshipEvidence(entityId),
    enabled: Boolean(entityId),
  });
  if (query.isLoading) return <LoadingState label="Loading relationship evidence" />;
  if (query.error) return <ErrorState error={query.error} />;
  if (!query.data?.items.length) {
    return <EmptyState title="No relationship evidence" detail="No evidence is linked yet." />;
  }
  return <div className="table-wrap"><table><thead><tr>
    <th>Source record</th><th>Direction</th><th>Type</th><th>Published</th>
    <th>Confidence</th><th>Reference</th>
  </tr></thead><tbody>{query.data.items.map((item) => <tr key={`${item.id}-${item.relationship_id}`}>
    <td>{item.source_record_identifier}</td><td>{item.direction}</td>
    <td>{item.evidence_type}</td><td>{new Date(item.publication_time).toLocaleDateString()}</td>
    <td>{Math.round(Number(item.confidence) * 100)}%</td><td>{item.content_reference}</td>
  </tr>)}</tbody></table></div>;
}
