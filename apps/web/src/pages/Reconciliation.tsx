import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import { EmptyState, ErrorState, LoadingState } from "../components/States";

export function Reconciliation() {
  const queryClient = useQueryClient();
  const reportsQuery = useQuery({ queryKey: ["reconciliation-reports"], queryFn: api.reconciliationReports });
  const preview = useMutation({ mutationFn: () => api.reconciliationPreview({ dry_run: true }) });
  const run = useMutation({
    mutationFn: () => api.reconciliationRun({ dry_run: false }),
    onSuccess: async () => queryClient.invalidateQueries({ queryKey: ["reconciliation-reports"] }),
  });
  if (reportsQuery.isLoading) return <LoadingState label="Loading reconciliation reports" />;
  if (reportsQuery.error) return <ErrorState error={reportsQuery.error} />;
  const reports = reportsQuery.data ?? [];
  const previewIssues = preview.data?.issues ?? [];
  return <section><div className="page-heading"><div><p className="eyebrow">DATA QUALITY</p><h1>Reconciliation</h1><p>Detect gaps, stale bars, closed sessions, invalid values, and checksum conflicts without silent overwrite.</p></div><div className="button-row"><button className="secondary" type="button" disabled={preview.isPending} onClick={() => preview.mutate()}>{preview.isPending ? "Checking…" : "Dry-run preview"}</button><button type="button" disabled={run.isPending} onClick={() => run.mutate()}>{run.isPending ? "Recording…" : "Record reconciliation"}</button></div></div>
    {preview.data ? <article className="panel" aria-live="polite"><h2>Preview</h2><div className="metric-grid"><article><span>Records checked</span><strong>{preview.data.records_checked}</strong></article><article><span>Issues</span><strong>{preview.data.issue_count}</strong></article><article><span>Conflicts</span><strong>{preview.data.conflict_count ?? 0}</strong></article></div>{previewIssues.length === 0 ? <p>No issues detected.</p> : <div className="table-card"><table><thead><tr><th>Severity</th><th>Type</th><th>Record</th></tr></thead><tbody>{previewIssues.map((issue, index) => <tr key={`${issue.type}-${issue.record}-${index}`}><td>{issue.severity}</td><td>{issue.type}</td><td>{issue.record}</td></tr>)}</tbody></table></div>}</article> : null}
    {preview.error ? <p className="validation-error" role="alert">{preview.error.message}</p> : null}{run.error ? <p className="validation-error" role="alert">{run.error.message}</p> : null}
    <h2 className="section-title">Recorded reports</h2>{reports.length === 0 ? <EmptyState title="No reconciliation reports" detail="Run a dry preview or record the first report." /> : <div className="table-card"><table><thead><tr><th>Run</th><th>Status</th><th>Mode</th><th>Records</th><th>Issues</th></tr></thead><tbody>{reports.map(report => <tr key={report.id}><td>{report.id?.slice(0, 8)}</td><td>{report.status}</td><td>{report.dry_run ? "Dry run" : "Recorded"}</td><td>{report.records_checked}</td><td>{report.issue_count}</td></tr>)}</tbody></table></div>}
  </section>;
}
