import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import { useAuth } from "../auth";

export function AuditLog() {
  const { workspace } = useAuth();
  const query = useQuery({ queryKey: ["audit", workspace?.id], queryFn: () => api.auditEvents(workspace!.id), enabled: Boolean(workspace) });
  if (query.error) return <section><h1>Audit log</h1><p role="alert">Audit log access is forbidden for this role.</p></section>;
  return <section><h1>Immutable audit log</h1><table><thead><tr><th>Time</th><th>Action</th><th>Resource</th><th>Result</th></tr></thead><tbody>
    {query.data?.items.map((event) => <tr key={event.id}><td>{event.timestamp}</td><td>{event.action}</td><td>{event.resource_type}</td><td>{event.result}</td></tr>)}</tbody></table></section>;
}
