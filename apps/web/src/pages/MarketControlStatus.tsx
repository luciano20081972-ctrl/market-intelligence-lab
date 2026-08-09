import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import { ErrorState, LoadingState } from "../components/States";

export function MarketControlStatus() {
  const market = useQuery({ queryKey: ["market-control-status"], queryFn: api.marketControlStatus, refetchInterval: 15_000 });
  const signals = useQuery({ queryKey: ["decision-signals"], queryFn: api.decisionSignals, refetchInterval: 30_000 });
  const alerts = useQuery({ queryKey: ["alert-events"], queryFn: api.alertEvents, refetchInterval: 30_000 });
  if (market.isLoading || signals.isLoading || alerts.isLoading) return <LoadingState label="Loading market supervisor" />;
  const error = market.error || signals.error || alerts.error;
  if (error) return <ErrorState error={error} />;
  return <section><div className="page-heading"><div><p className="eyebrow">ALWAYS-ON INTELLIGENCE</p><h1>Market status</h1><p>Session-aware monitoring, freshness classifications, decision support, and in-app alerts. Research and paper trading only.</p></div><span className="health large"><i />{market.data!.supervisor.status}</span></div>
    <div className="metric-grid"><article className="metric"><span>Market session</span><strong>{market.data!.supervisor.session_state}</strong></article><article className="metric"><span>Signals</span><strong>{signals.data!.length}</strong></article><article className="metric"><span>Alerts</span><strong>{alerts.data!.length}</strong></article><article className="metric"><span>Last heartbeat</span><strong className="compact-value">{market.data!.supervisor.heartbeat_at ? new Date(market.data!.supervisor.heartbeat_at).toLocaleTimeString() : "none"}</strong></article></div>
    <div className="panel-grid"><article className="panel"><h2>Feed freshness</h2><p>Delayed, stale, and unknown inputs are never represented as real-time.</p><dl className="detail-list">{Object.entries(market.data!.freshness_last_two_minutes).map(([key, count]) => <div key={key}><dt>{key}</dt><dd>{count}</dd></div>)}{Object.keys(market.data!.freshness_last_two_minutes).length === 0 && <div><dt>No recent observations</dt><dd>UNKNOWN</dd></div>}</dl></article><article className="panel"><h2>Supervisor</h2><dl className="detail-list"><div><dt>Instance</dt><dd>{market.data!.supervisor.instance_id ?? "not running"}</dd></div><div><dt>Local provider</dt><dd>{market.data!.supervisor.providers.local ?? "unknown"}</dd></div><div><dt>Cloud Run</dt><dd>{market.data!.supervisor.providers.cloud_run ?? "unknown"}</dd></div><div><dt>Last signal scan</dt><dd>{market.data!.supervisor.last_signal_scan_at ? new Date(market.data!.supervisor.last_signal_scan_at).toLocaleString() : "not scheduled"}</dd></div><div><dt>Last error</dt><dd>{market.data!.supervisor.last_error ?? "none"}</dd></div></dl></article></div>
    <div className="disclaimer"><b>Decision support only.</b> Signals are simulated research outputs, not guarantees or real brokerage instructions.</div>
  </section>;
}
