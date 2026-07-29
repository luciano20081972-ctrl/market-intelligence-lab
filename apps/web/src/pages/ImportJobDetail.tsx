import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { api } from "../api";
import { ErrorState, LoadingState } from "../components/States";

export function ImportJobDetail() {
  const { id = "" } = useParams();
  const client = useQueryClient();
  const query = useQuery({ queryKey: ["import-job", id], queryFn: () => api.importJob(id), enabled: Boolean(id) });
  const refresh = () => client.invalidateQueries({ queryKey: ["import-job", id] });
  const cancel = useMutation({ mutationFn: () => api.cancelImportJob(id), onSuccess: refresh });
  const restart = useMutation({ mutationFn: () => api.restartImportJob(id), onSuccess: refresh });
  if (query.isLoading) return <LoadingState label="Loading import detail" />;
  if (query.error) return <ErrorState error={query.error} />;
  const job = query.data!;
  const canCancel = ["queued", "running", "retrying"].includes(job.status);
  const canRestart = ["failed", "retrying", "interrupted", "cancelled"].includes(job.status);
  return <section><div className="page-heading"><div><p className="eyebrow">IMPORT {job.id.slice(0, 8)}</p><h1>{job.provider_code} · {job.status}</h1><p>{job.mode} import for {job.symbols.join(", ")}</p></div><div className="button-row"><button type="button" className="secondary" disabled={!canCancel || cancel.isPending} onClick={() => cancel.mutate()}>Cancel</button><button type="button" disabled={!canRestart || restart.isPending} onClick={() => restart.mutate()}>Restart</button></div></div>
    <div className="metric-grid"><article><span>Processed</span><strong>{job.records_processed}</strong></article><article><span>Inserted</span><strong>{job.records_inserted}</strong></article><article><span>Skipped</span><strong>{job.records_skipped}</strong></article><article><span>Duration</span><strong>{job.processing_duration_ms} ms</strong></article></div>
    {job.error_summary ? <div className="state-card error" role="alert">{job.error_summary}</div> : null}
    <h2 className="section-title">Batches</h2><div className="table-card"><table><thead><tr><th>#</th><th>Status</th><th>Processed</th><th>Inserted</th><th>Skipped</th><th>Checksum</th></tr></thead><tbody>{job.batches.map(batch => <tr key={batch.id}><td>{batch.sequence + 1}</td><td>{batch.status}</td><td>{batch.records_processed}</td><td>{batch.records_inserted}</td><td>{batch.records_skipped}</td><td><code>{batch.checksum.slice(0, 12) || "pending"}</code></td></tr>)}</tbody></table></div>
  </section>;
}
