import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router";
import { api } from "../api";
import { ErrorState, LoadingState } from "../components/States";

export function ComputeJobDetail() {
  const { id = "" } = useParams();
  const client = useQueryClient();
  const job = useQuery({ queryKey: ["compute-job", id], queryFn: () => api.computeJob(id), refetchInterval: 10_000 });
  const cancel = useMutation({ mutationFn: () => api.cancelComputeJob(id), onSuccess: () => void client.invalidateQueries({ queryKey: ["compute-job", id] }) });
  const retry = useMutation({ mutationFn: () => api.retryComputeJob(id), onSuccess: () => void client.invalidateQueries({ queryKey: ["compute-job", id] }) });
  if (job.isLoading) return <LoadingState label="Loading compute job" />;
  if (job.error) return <ErrorState error={job.error} />;
  const value = job.data!;
  return <section className="narrow"><Link className="back-link" to="/compute">← Compute status</Link><div className="page-heading"><div><p className="eyebrow">JOB DETAIL</p><h1>{value.job_type}</h1><p>{value.submission_key}</p></div><span className="tag">{value.state}</span></div>
    <div className="panel-grid"><article className="panel"><h2>Routing</h2><dl className="detail-list"><div><dt>Class</dt><dd>{value.job_class}</dd></div><div><dt>Provider</dt><dd>{value.selected_provider ?? "none"}</dd></div><div><dt>Priority</dt><dd>{value.priority}</dd></div><div><dt>Retries</dt><dd>{value.attempt_count} / {value.max_attempts}</dd></div><div><dt>Decision</dt><dd>{value.transitions?.at(-1)?.reason ?? value.state}</dd></div></dl></article><article className="panel"><h2>Resource estimate</h2><dl className="detail-list"><div><dt>CPU</dt><dd>{value.estimate.cpu}</dd></div><div><dt>RAM</dt><dd>{value.estimate.ram_mb} MiB</dd></div><div><dt>Runtime</dt><dd>{value.estimate.runtime_seconds}s</dd></div><div><dt>Estimated cost</dt><dd>${value.estimate.estimated_cost_usd}</dd></div><div><dt>Observed cost</dt><dd>{value.observed_cost_usd ? `$${value.observed_cost_usd}` : "billing pending"}</dd></div></dl></article></div>
    <article className="panel"><h2>Input and result validation</h2><p>Input manifest SHA-256: <code>{value.input_manifest_hash || "computed on submission"}</code></p><h3>Input manifest</h3><pre className="json-block">{JSON.stringify(value.input_manifest ?? {}, null, 2)}</pre><h3>Validated result manifest</h3><pre className="json-block">{JSON.stringify(value.result_manifest, null, 2)}</pre>{value.error_detail && <p className="validation-error">{value.error_classification}: {value.error_detail}</p>}</article>
    {value.transitions && value.transitions.length > 0 && <article className="panel"><h2>Auditable progress</h2><ol className="timeline">{value.transitions.map((transition, index) => <li key={`${transition.created_at}-${index}`}><b>{transition.to_state}</b><p>{transition.reason}</p><time>{new Date(transition.created_at).toLocaleString()}</time></li>)}</ol></article>}
    <div className="actions">{value.state === "FAILED_RETRYABLE" && <button onClick={() => retry.mutate()} disabled={retry.isPending}>Retry safely</button>}{!new Set(["SUCCEEDED", "FAILED_FINAL", "CANCELED"]).has(value.state) && <button className="danger-button" onClick={() => cancel.mutate()} disabled={cancel.isPending || value.cancel_requested}>{value.cancel_requested ? "Cancellation queued" : "Cancel job"}</button>}</div>
    {retry.error && <p className="validation-error">{retry.error.message}</p>}
  </section>;
}
