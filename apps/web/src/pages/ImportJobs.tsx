import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api";
import { EmptyState, ErrorState, LoadingState } from "../components/States";

export function ImportJobs() {
  const client = useQueryClient();
  const query = useQuery({ queryKey: ["import-jobs"], queryFn: api.importJobs });
  const [symbols, setSymbols] = useState("AAPL,MSFT");
  const [mode, setMode] = useState("incremental");
  const [start, setStart] = useState("2026-07-01");
  const [end, setEnd] = useState("2026-07-15");
  const create = useMutation({ mutationFn: api.createImportJob, onSuccess: () => client.invalidateQueries({ queryKey: ["import-jobs"] }) });
  function submit(event: FormEvent) {
    event.preventDefault();
    create.mutate({ provider_code: "synthetic", symbols: symbols.split(",").map(value => value.trim()).filter(Boolean), mode, start: start + "T00:00:00Z", end: end + "T23:59:59Z", interval: "1d", execute_immediately: true });
  }
  if (query.isLoading) return <LoadingState label="Loading import jobs" />;
  if (query.error) return <ErrorState error={query.error} />;
  const jobs = query.data?.items ?? [];
  return <section><div className="page-heading"><div><p className="eyebrow">INGESTION</p><h1>Import jobs</h1><p>Run full or incremental imports with durable status, retry, cancellation, and restart state.</p></div></div>
    <form className="panel research-form" onSubmit={submit}><div className="form-grid"><label>Symbols<input aria-label="Symbols" value={symbols} onChange={event => setSymbols(event.target.value)} /></label><label>Mode<select aria-label="Import mode" value={mode} onChange={event => setMode(event.target.value)}><option value="incremental">Incremental</option><option value="full">Full</option></select></label><label>Start<input aria-label="Import start" type="date" value={start} onChange={event => setStart(event.target.value)} /></label><label>End<input aria-label="Import end" type="date" value={end} onChange={event => setEnd(event.target.value)} /></label></div><div className="form-actions"><p>Synthetic is the only enabled provider in v0.3.0.</p><button type="submit" disabled={create.isPending}>{create.isPending ? "Importing…" : "Create import"}</button></div>{create.error ? <p className="validation-error" role="alert">{create.error.message}</p> : null}</form>
    {jobs.length === 0 ? <EmptyState title="No import history" detail="Create the first deterministic import above." /> : <div className="table-card"><table><thead><tr><th>Provider</th><th>Mode</th><th>Symbols</th><th>Status</th><th>Progress</th><th>Requested</th></tr></thead><tbody>{jobs.map(job => <tr key={job.id}><td><Link to={"/imports/" + job.id}>{job.provider_code}</Link></td><td>{job.mode}</td><td>{job.symbols.join(", ")}</td><td><span className="status-chip">{job.status}</span></td><td>{job.records_inserted} inserted · {job.records_skipped} skipped</td><td>{new Date(job.requested_at).toLocaleString()}</td></tr>)}</tbody></table></div>}
  </section>;
}
