import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { api } from "../api";
import { ErrorState, LoadingState } from "../components/States";

const terminal = new Set(["SUCCEEDED", "FAILED_FINAL", "CANCELED"]);
const blocked = new Set(["BLOCKED_BY_BUDGET", "WAITING_FOR_CAPACITY", "CLOUD_DISABLED"]);

export function ComputeDashboard() {
  const status = useQuery({ queryKey: ["compute-status"], queryFn: api.computeStatus, refetchInterval: 15_000 });
  const jobs = useQuery({ queryKey: ["compute-jobs"], queryFn: api.computeJobs, refetchInterval: 15_000 });
  const budget = useQuery({ queryKey: ["cloud-budget"], queryFn: api.cloudBudget, refetchInterval: 30_000 });
  if (status.isLoading || jobs.isLoading || budget.isLoading) return <LoadingState label="Loading compute control plane" />;
  const error = status.error || jobs.error || budget.error;
  if (error) return <ErrorState error={error} />;
  const queued = jobs.data!.filter((job) => job.state === "QUEUED").length;
  const running = jobs.data!.filter((job) => job.state.endsWith("RUNNING")).length;
  const completed = jobs.data!.filter((job) => terminal.has(job.state)).length;
  const held = jobs.data!.filter((job) => blocked.has(job.state)).length;
  return <section>
    <div className="page-heading"><div><p className="eyebrow">ELASTIC RESEARCH</p><h1>Compute status</h1><p>The Dell remains the local control plane. Heavy jobs wait safely when cloud compute is disabled or over budget.</p></div><span className={`health large ${status.data!.cloud_enabled ? "" : "warning"}`}><i />Cloud {status.data!.cloud_enabled ? "enabled" : "disabled"}</span></div>
    <div className="metric-grid"><article className="metric"><span>Queued</span><strong>{queued}</strong></article><article className="metric"><span>Running</span><strong>{running}</strong></article><article className="metric"><span>Completed</span><strong>{completed}</strong></article><article className="metric"><span>Blocked / waiting</span><strong>{held}</strong></article></div>
    <div className="panel-grid">
      <article className="panel"><div className="panel-title"><div><h2>Providers and local guard</h2><p>Capacity reserved for the API, database, reader, SSH, and monitoring.</p></div></div><dl className="detail-list"><div><dt>Local provider</dt><dd>{status.data!.providers.local}</dd></div><div><dt>Cloud Run</dt><dd>{status.data!.providers.cloud_run}</dd></div><div><dt>Available RAM</dt><dd>{status.data!.resource_guard.available_ram_mb} MiB</dd></div><div><dt>Load per CPU</dt><dd>{status.data!.resource_guard.load_per_cpu.toFixed(2)}</dd></div><div><dt>Analytical jobs</dt><dd>{status.data!.resource_guard.running_analytical_jobs}</dd></div></dl></article>
      <article className="panel"><div className="panel-title"><div><h2>Cloud budget</h2><p>Usage is estimated and provider billing can lag.</p></div></div><dl className="detail-list"><div><dt>Per job limit</dt><dd>${budget.data!.limits.job_usd}</dd></div><div><dt>Daily estimate</dt><dd>${budget.data!.usage.daily_usd} / ${budget.data!.limits.daily_usd}</dd></div><div><dt>Monthly estimate</dt><dd>${budget.data!.usage.monthly_usd} / ${budget.data!.limits.monthly_usd}</dd></div><div><dt>Parallel tasks</dt><dd>{budget.data!.usage.active_tasks} / {budget.data!.limits.parallel_tasks}</dd></div></dl></article>
    </div>
    <h2 className="section-title">Durable jobs</h2>
    <div className="table-card"><table><thead><tr><th>Job</th><th>Class</th><th>State</th><th>Provider</th><th>Estimate</th><th>Attempts</th></tr></thead><tbody>{jobs.data!.map((job) => <tr key={job.id}><td><Link className="symbol" to={`/compute/jobs/${job.id}`}>{job.job_type}</Link><small>{job.submission_key}</small></td><td>{job.job_class}</td><td><span className="tag">{job.state}</span></td><td>{job.selected_provider ?? "not selected"}</td><td>${job.estimate.estimated_cost_usd} · {job.estimate.ram_mb} MiB</td><td>{job.attempt_count} / {job.max_attempts}</td></tr>)}</tbody></table>{jobs.data!.length === 0 && <p className="empty-table">No compute jobs have been submitted.</p>}</div>
  </section>;
}
