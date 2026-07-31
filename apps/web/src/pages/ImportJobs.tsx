import { FormEvent, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router";
import { api } from "../api";
import { EmptyState, ErrorState, LoadingState } from "../components/States";

export function ImportJobs() {
  const queryClient = useQueryClient();
  const jobsQuery = useQuery({ queryKey: ["import-jobs"], queryFn: api.importJobs });
  const providersQuery = useQuery({ queryKey: ["providers"], queryFn: api.providers });
  const providers = useMemo(
    () => (providersQuery.data?.items ?? []).filter(provider => provider.is_enabled),
    [providersQuery.data],
  );
  const [providerCode, setProviderCode] = useState("synthetic");
  const [symbols, setSymbols] = useState("AAPL,MSFT");
  const [mode, setMode] = useState("incremental");
  const [start, setStart] = useState("2026-07-06");
  const [end, setEnd] = useState("2026-08-14");
  const [adjustment, setAdjustment] = useState("provider_default");
  const [dryRun, setDryRun] = useState(false);
  const [previewSignature, setPreviewSignature] = useState<string | null>(null);
  const normalizedSymbols = useMemo(
    () => symbols.split(",").map(value => value.trim().toUpperCase()).filter(Boolean),
    [symbols],
  );
  const activeProviderCode = providers.some(provider => provider.code === providerCode)
    ? providerCode
    : providers[0]?.code ?? providerCode;
  const payload = {
    provider_code: activeProviderCode,
    symbols: normalizedSymbols,
    mode,
    start: `${start}T00:00:00Z`,
    end: `${end}T23:59:59Z`,
    interval: "1d",
    adjustment_preference: adjustment,
    dry_run: dryRun,
  };
  const payloadSignature = JSON.stringify(payload);
  const preview = useMutation({
    mutationFn: (request: typeof payload) => api.previewImport(request),
    onSuccess: (_result, request) => setPreviewSignature(JSON.stringify(request)),
    onError: () => setPreviewSignature(null),
  });
  const canQueue = activeProviderCode === "synthetic"
    || (preview.data?.can_submit === true && previewSignature === payloadSignature);
  const create = useMutation({
    mutationFn: () => api.createImportJob({ ...payload, execute_immediately: false }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["import-jobs"] });
    },
  });
  function submit(event: FormEvent) {
    event.preventDefault();
    if (!canQueue) return;
    create.mutate();
  }
  if (jobsQuery.isLoading || providersQuery.isLoading) {
    return <LoadingState label="Loading import operations" />;
  }
  if (jobsQuery.error) return <ErrorState error={jobsQuery.error} />;
  if (providersQuery.error) return <ErrorState error={providersQuery.error} />;
  const jobs = jobsQuery.data?.items ?? [];
  return <section><div className="page-heading"><div><p className="eyebrow">INGESTION</p><h1>Historical imports</h1><p>Preview validation, then enqueue a durable full or incremental import.</p></div><Link className="button-link secondary" to="/operations">Queue dashboard</Link></div>
    <form className="panel research-form" onSubmit={submit}><div className="form-grid"><label>Provider<select aria-label="Provider" value={activeProviderCode} onChange={event => { setProviderCode(event.target.value); setPreviewSignature(null); preview.reset(); }}>{providers.map(provider => <option key={provider.id} value={provider.code}>{provider.name}</option>)}</select></label><label>Symbols<input aria-label="Symbols" value={symbols} onChange={event => setSymbols(event.target.value)} /></label><label>Mode<select aria-label="Import mode" value={mode} onChange={event => setMode(event.target.value)}><option value="incremental">Incremental</option><option value="full">Full</option></select></label><label>Adjustment<select aria-label="Adjustment preference" value={adjustment} onChange={event => setAdjustment(event.target.value)}><option value="provider_default">Provider default</option><option value="unadjusted">Unadjusted</option><option value="adjusted">Adjusted</option></select></label><label>Start<input aria-label="Import start" type="date" value={start} onChange={event => setStart(event.target.value)} /></label><label>End<input aria-label="Import end" type="date" value={end} onChange={event => setEnd(event.target.value)} /></label><label className="checkbox-label"><input aria-label="Dry run" type="checkbox" checked={dryRun} onChange={event => setDryRun(event.target.checked)} />Dry run; persist no bars</label></div><div className="form-actions"><p>{activeProviderCode === "synthetic" ? "Submission is queued; run the documented worker to process it." : "External imports require a successful preview for this exact request before queuing."}</p><div className="button-row"><button className="secondary" type="button" disabled={preview.isPending || normalizedSymbols.length === 0} onClick={() => preview.mutate(payload)}>{preview.isPending ? "Previewing…" : "Preview import"}</button><button type="submit" disabled={create.isPending || normalizedSymbols.length === 0 || !canQueue}>{create.isPending ? "Queuing…" : "Queue import"}</button></div></div>{preview.data ? <div className="preview-card" aria-live="polite"><strong>{preview.data.can_submit ? "Preview passed" : "Preview found issues"}</strong><ul>{preview.data.reports.map(report => <li key={report.symbol}>{report.symbol} → {report.provider_symbol ?? report.symbol}: {report.records} records, {report.valid ? "valid" : report.error ?? "invalid"}</li>)}</ul></div> : null}{preview.error ? <p className="validation-error" role="alert">{preview.error.message}</p> : null}{create.error ? <p className="validation-error" role="alert">{create.error.message}</p> : null}{create.data ? <p className="success-message" role="status">Job {create.data.id.slice(0, 8)} queued successfully.</p> : null}</form>
    {jobs.length === 0 ? <EmptyState title="No import history" detail="Preview and queue the first deterministic import above." /> : <div className="table-card"><table><thead><tr><th>Provider</th><th>Mode</th><th>Symbols</th><th>Status</th><th>Progress</th><th>Requested</th></tr></thead><tbody>{jobs.map(job => <tr key={job.id}><td><Link to={`/imports/${job.id}`}>{job.provider_code}</Link></td><td>{job.mode}{job.dry_run ? " · dry run" : ""}</td><td>{job.symbols.join(", ")}</td><td><span className="status-chip">{job.status}</span></td><td>{job.records_inserted} inserted · {job.records_skipped} skipped</td><td>{new Date(job.requested_at).toLocaleString()}</td></tr>)}</tbody></table></div>}
  </section>;
}
