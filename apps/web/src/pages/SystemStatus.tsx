import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import { ErrorState, LoadingState } from "../components/States";

export function SystemStatus() {
  const health = useQuery({ queryKey: ["health"], queryFn: api.health, refetchInterval: 30_000 });
  const info = useQuery({ queryKey: ["system-info"], queryFn: api.systemInfo });
  if (health.isLoading || info.isLoading) return <LoadingState label="Checking system health" />;
  const error = health.error || info.error;
  if (error) return <ErrorState error={error} />;
  return <section><div className="page-heading"><div><p className="eyebrow">OPERATIONS</p><h1>System status</h1><p>Local runtime health with no environment values or secrets exposed.</p></div><span className="health large"><i />All local services operational</span></div><div className="source-grid"><article className="panel"><h2>API</h2><strong className="status-value">{health.data!.status}</strong><p>Version {health.data!.version}</p></article><article className="panel"><h2>Database</h2><strong className="status-value">{health.data!.database}</strong><p>{info.data!.database_engine} engine</p></article><article className="panel"><h2>Runtime</h2><strong className="status-value">{info.data!.environment}</strong><p>Demonstration mode {info.data!.demonstration_mode ? "enabled" : "disabled"}</p></article></div></section>;
}
