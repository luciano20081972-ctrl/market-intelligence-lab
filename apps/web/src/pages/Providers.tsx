import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router";
import { api } from "../api";
import { EmptyState, ErrorState, LoadingState } from "../components/States";

export function Providers() {
  const client = useQueryClient();
  const query = useQuery({ queryKey: ["providers"], queryFn: api.providers });
  const test = useMutation({
    mutationFn: (providerId: string) => api.testProvider(providerId),
    onSuccess: () => client.invalidateQueries({ queryKey: ["providers"] }),
  });
  if (query.isLoading) return <LoadingState label="Loading provider registry" />;
  if (query.error) return <ErrorState error={query.error} />;
  const providers = query.data?.items ?? [];
  return <section><div className="page-heading"><div><p className="eyebrow">MARKET DATA</p><h1>Providers</h1><p>Registered data capabilities, configuration state, and safe health checks.</p></div></div>
    {providers.length === 0 ? <EmptyState title="No providers registered" detail="Seed the provider registry to begin." /> : <div className="source-grid">{providers.map(provider => <article className="panel" key={provider.id}><div className="panel-title"><div><p className="eyebrow">{provider.code}</p><h2><Link to={`/providers/${provider.id}`}>{provider.name}</Link></h2></div><span className={provider.health === "healthy" ? "health" : "status-chip"}>{provider.health}</span></div><dl className="detail-list"><div><dt>Enabled</dt><dd>{provider.is_enabled ? "Yes" : "No"}</dd></div><div><dt>Credentials</dt><dd>{provider.authentication_required ? "Required" : "None"}</dd></div><div><dt>Last sync</dt><dd>{provider.last_successful_import_at ? new Date(provider.last_successful_import_at).toLocaleString() : "Never"}</dd></div></dl><p>{provider.capabilities.join(" · ")}</p><p className="license-note">Credentials are referenced by environment variable name only: {provider.credential_environment_keys.join(", ") || "none"}.</p><div className="button-row"><Link className="button-link secondary" to={`/providers/${provider.id}`}>Details</Link><button className="secondary" type="button" disabled={test.isPending} onClick={() => test.mutate(provider.id)}>Test provider</button></div></article>)}</div>}
  </section>;
}
