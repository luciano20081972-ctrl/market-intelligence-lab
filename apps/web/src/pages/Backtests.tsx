import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api";
import { EmptyState, ErrorState, LoadingState } from "../components/States";

export function Backtests() {
  const query = useQuery({ queryKey: ["backtests"], queryFn: api.backtests });
  if (query.isLoading) return <LoadingState label="Loading backtest history" />;
  if (query.error) return <ErrorState error={query.error} />;
  return <section><div className="page-heading"><div><p className="eyebrow">REPRODUCIBLE RUNS</p><h1>Backtests</h1><p>Every result records its strategy version, data provenance, and execution assumptions.</p></div><Link className="button" to="/strategies">New backtest</Link></div>
    {!query.data!.items.length ? <EmptyState title="No backtests yet" detail="Open Strategy Lab to run the first simulation." /> : <div className="table-card"><table><thead><tr><th>Strategy</th><th>Universe</th><th>Period</th><th className="number">Final equity</th><th className="number">Return</th><th>Status</th></tr></thead><tbody>{query.data!.items.map(run => <tr key={run.id}><td><Link className="symbol" to={`/backtests/${run.id}`}>{run.strategy_name}<small>{new Date(run.created_at).toLocaleString()}</small></Link></td><td>{run.asset_symbols.join(", ")}</td><td>{new Date(run.start_time).toLocaleDateString()} – {new Date(run.end_time).toLocaleDateString()}</td><td className="number">${Number(run.final_equity).toLocaleString(undefined, { maximumFractionDigits: 2 })}</td><td className="number">{(Number(run.metrics.total_return ?? 0) * 100).toFixed(2)}%</td><td><span className="health"><i />{run.status}</span></td></tr>)}</tbody></table></div>}
  </section>;
}
