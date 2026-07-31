import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router";
import { api } from "../api";
import { ErrorState, LoadingState } from "../components/States";

export function ProviderDetail() {
  const { id = "" } = useParams();
  const queryClient = useQueryClient();
  const providerQuery = useQuery({
    queryKey: ["provider", id],
    queryFn: () => api.provider(id),
    enabled: Boolean(id),
  });
  const statusQuery = useQuery({
    queryKey: ["provider-status", id],
    queryFn: () => api.providerStatus(id),
    enabled: Boolean(id),
  });
  const test = useMutation({
    mutationFn: () => api.testProvider(id),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["provider", id] }),
        queryClient.invalidateQueries({ queryKey: ["provider-status", id] }),
      ]);
    },
  });
  if (providerQuery.isLoading || statusQuery.isLoading) {
    return <LoadingState label="Loading provider operations" />;
  }
  if (providerQuery.error) return <ErrorState error={providerQuery.error} />;
  if (statusQuery.error) return <ErrorState error={statusQuery.error} />;
  const provider = providerQuery.data!;
  const status = statusQuery.data!;
  const diagnosticHealth = test.data?.status ?? status.health;
  const diagnosticConnectivity = test.data?.connectivity ?? status.connectivity;
  const diagnosticClassification = test.data?.response_classification
    ?? status.response_classification;
  const diagnosticSchema = test.data?.schema_compatible ?? status.schema_compatible;
  const diagnosticMessage = test.data?.message ?? status.message;
  return <section>
    <div className="page-heading"><div><p className="eyebrow">PROVIDER DETAIL</p><h1>{provider.name}</h1><p>Read-only historical data through the fixed {provider.code} adapter.</p></div><Link className="button-link secondary" to="/providers">All providers</Link></div>
    {provider.code === "stooq" && <div className="disclaimer"><strong>Live Stooq availability is not verified.</strong><p>The endpoint previously returned an HTML access page; fixture parsing is verified, but no valid live bars were imported.</p></div>}
    {provider.code === "twelve_data" && <div className="disclaimer"><strong>Twelve Data is fixture-tested, not live-verified.</strong><p>A bounded live smoke test requires an explicit API key and opt-in. Redistribution rights are not claimed.</p></div>}
    <div className="metric-grid"><article><span>Configuration</span><strong>{provider.configuration_status}</strong></article><article><span>Health</span><strong>{diagnosticHealth}</strong></article><article><span>Connectivity</span><strong>{diagnosticConnectivity}</strong></article><article><span>Freshness</span><strong>{status.stale ? "stale / never synced" : "current"}</strong></article></div>
    <div className="detail-grid"><article className="panel"><h2>Connection</h2><dl className="detail-list"><div><dt>Authentication</dt><dd>{provider.authentication_required ? "Environment credential required" : "No API key required"}</dd></div><div><dt>Adapter</dt><dd>{provider.adapter_type}</dd></div><div><dt>Response class</dt><dd>{diagnosticClassification ?? "not_tested"}</dd></div><div><dt>Schema compatible</dt><dd>{diagnosticSchema == null ? "unknown" : diagnosticSchema ? "yes" : "no"}</dd></div><div><dt>Last test</dt><dd>{status.last_checked_at ? new Date(status.last_checked_at).toLocaleString() : "Not tested"}</dd></div><div><dt>Last successful sync</dt><dd>{status.last_successful_import_at ? new Date(status.last_successful_import_at).toLocaleString() : "Never"}</dd></div></dl>{diagnosticMessage ? <p className={diagnosticHealth === "healthy" ? "success-message" : "validation-error"} role="status">{diagnosticMessage}</p> : null}<button type="button" disabled={test.isPending} onClick={() => test.mutate()}>{test.isPending ? "Testing…" : "Test connection"}</button>{test.error ? <p className="validation-error" role="alert">{test.error.message}</p> : null}</article>
      <article className="panel"><h2>Capabilities</h2><p>{provider.capabilities.join(" · ")}</p><p className="license-note">Provider terms and redistribution rights require an independent review. Market Intelligence Lab does not claim commercial redistribution rights.</p><Link className="button-link" to="/imports">Preview historical import</Link></article></div>
  </section>;
}
