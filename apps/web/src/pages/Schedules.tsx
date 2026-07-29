import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import { EmptyState, ErrorState, LoadingState } from "../components/States";

export function Schedules() {
  const queryClient = useQueryClient();
  const schedulesQuery = useQuery({ queryKey: ["import-schedules"], queryFn: api.schedules });
  const providersQuery = useQuery({ queryKey: ["providers"], queryFn: api.providers });
  const [name, setName] = useState("Daily AAPL");
  const [symbols, setSymbols] = useState("AAPL");
  const [providerId, setProviderId] = useState("");
  const [timezone, setTimezone] = useState("America/New_York");
  const create = useMutation({
    mutationFn: (payload: Record<string, unknown>) => api.createSchedule(payload),
    onSuccess: async () => queryClient.invalidateQueries({ queryKey: ["import-schedules"] }),
  });
  const toggle = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) => api.updateSchedule(id, { is_enabled: enabled }),
    onSuccess: async () => queryClient.invalidateQueries({ queryKey: ["import-schedules"] }),
  });
  const runNow = useMutation({ mutationFn: api.runScheduleNow, onSuccess: async () => queryClient.invalidateQueries({ queryKey: ["import-schedules"] }) });
  const remove = useMutation({ mutationFn: api.deleteSchedule, onSuccess: async () => queryClient.invalidateQueries({ queryKey: ["import-schedules"] }) });
  if (schedulesQuery.isLoading || providersQuery.isLoading) return <LoadingState label="Loading import schedules" />;
  if (schedulesQuery.error) return <ErrorState error={schedulesQuery.error} />;
  if (providersQuery.error) return <ErrorState error={providersQuery.error} />;
  const providers = (providersQuery.data?.items ?? []).filter(provider => provider.is_enabled);
  const selectedProvider = providerId || providers[0]?.id || "";
  const schedules = schedulesQuery.data ?? [];
  function submit(event: FormEvent) {
    event.preventDefault();
    create.mutate({ provider_id: selectedProvider, name, symbols: symbols.split(",").map(value => value.trim().toUpperCase()).filter(Boolean), mode: "incremental", adjustment_preference: "provider_default", timezone, next_run_at: new Date(Date.now() + 86_400_000).toISOString(), lookback_days: 7, is_enabled: true });
  }
  return <section><div className="page-heading"><div><p className="eyebrow">AUTOMATION</p><h1>Import schedules</h1><p>Persisted daily schedules create idempotent jobs for each due time.</p></div></div>
    <form className="panel research-form" onSubmit={submit}><div className="form-grid"><label>Name<input aria-label="Schedule name" value={name} onChange={event => setName(event.target.value)} /></label><label>Provider<select aria-label="Schedule provider" value={selectedProvider} onChange={event => setProviderId(event.target.value)}>{providers.map(provider => <option key={provider.id} value={provider.id}>{provider.name}</option>)}</select></label><label>Symbols<input aria-label="Schedule symbols" value={symbols} onChange={event => setSymbols(event.target.value)} /></label><label>Timezone<input aria-label="Schedule timezone" value={timezone} onChange={event => setTimezone(event.target.value)} /></label></div><button type="submit" disabled={create.isPending || !selectedProvider}>{create.isPending ? "Creating…" : "Create daily schedule"}</button>{create.error ? <p className="validation-error" role="alert">{create.error.message}</p> : null}</form>
    {schedules.length === 0 ? <EmptyState title="No schedules" detail="Create a daily incremental import schedule above." /> : <div className="table-card"><table><thead><tr><th>Name</th><th>Scope</th><th>Next run</th><th>Status</th><th>Failures</th><th>Actions</th></tr></thead><tbody>{schedules.map(schedule => <tr key={schedule.id}><td>{schedule.name}<small>{schedule.timezone}</small></td><td>{schedule.symbols.join(", ")}</td><td>{new Date(schedule.next_run_at).toLocaleString()}</td><td>{schedule.is_enabled ? "Enabled" : "Disabled"}</td><td>{schedule.failure_count}</td><td><div className="button-row"><button className="secondary" type="button" onClick={() => toggle.mutate({ id: schedule.id, enabled: !schedule.is_enabled })}>{schedule.is_enabled ? "Disable" : "Enable"}</button><button className="secondary" type="button" onClick={() => runNow.mutate(schedule.id)}>Run now</button><button className="danger" type="button" onClick={() => remove.mutate(schedule.id)}>Delete</button></div></td></tr>)}</tbody></table></div>}
  </section>;
}
