import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import { EmptyState, ErrorState, LoadingState } from "../components/States";

export function DataQuality() {
  const jobs = useQuery({ queryKey: ["import-jobs"], queryFn: api.importJobs });
  const errors = useQuery({ queryKey: ["import-errors"], queryFn: api.importErrors });
  if (jobs.isLoading || errors.isLoading) return <LoadingState label="Calculating data quality" />;
  if (jobs.error) return <ErrorState error={jobs.error} />;
  if (errors.error) return <ErrorState error={errors.error} />;
  const jobItems = jobs.data?.items ?? [];
  const errorItems = errors.data?.items ?? [];
  const stale = jobItems.filter(job => !job.completed_at || Date.now() - new Date(job.completed_at).getTime() > 7 * 86400000).length;
  const failures = jobItems.reduce((total, job) => total + (job.validation_report.batches ?? []).reduce((sum, batch) => sum + batch.error_count, 0), 0);
  return <section><div className="page-heading"><div><p className="eyebrow">GOVERNANCE</p><h1>Data quality</h1><p>Validation failures, freshness, duplicate prevention, and import health.</p></div></div><div className="metric-grid"><article><span>Validation failures</span><strong>{failures}</strong></article><article><span>Import errors</span><strong>{errorItems.length}</strong></article><article><span>Stale imports</span><strong>{stale}</strong></article><article><span>Successful jobs</span><strong>{jobItems.filter(job => job.status === "succeeded").length}</strong></article></div>
    <h2 className="section-title">Latest failures</h2>{errorItems.length === 0 ? <EmptyState title="No validation errors" detail="Current imported records pass the enforced checks." /> : <div className="table-card"><table><thead><tr><th>Code</th><th>Message</th><th>Record</th><th>Retryable</th></tr></thead><tbody>{errorItems.map(error => <tr key={error.id}><td>{error.error_code}</td><td>{error.message}</td><td>{error.record_identifier ?? "job-level"}</td><td>{error.is_retryable ? "Yes" : "No"}</td></tr>)}</tbody></table></div>}
  </section>;
}
