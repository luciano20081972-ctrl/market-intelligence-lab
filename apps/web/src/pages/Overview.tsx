import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { api } from "../api";
import { ErrorState, LoadingState } from "../components/States";

const quickActions = [
  { to: "/watchlists", title: "View Watchlists", detail: "Open the companies and funds you follow." },
  { to: "/assets", title: "Research Markets", detail: "Explore price history and available market data." },
  { to: "/strategies", title: "Test a Strategy", detail: "Set assumptions and run a controlled historical test." },
  { to: "/backtests", title: "Review Backtests", detail: "Understand results, costs, and important limitations." },
  { to: "/paper-portfolios", title: "Open Paper Portfolio", detail: "Practice with simulated money before real decisions." },
];

export function Overview() {
  const info = useQuery({ queryKey: ["system-info"], queryFn: api.systemInfo });
  const health = useQuery({ queryKey: ["health"], queryFn: api.health });
  const sources = useQuery({ queryKey: ["sources"], queryFn: api.dataSources });
  const foundation = useQuery({ queryKey: ["market-foundation"], queryFn: api.marketFoundation });
  if (info.isLoading || health.isLoading || sources.isLoading || foundation.isLoading) return <LoadingState label="Loading your dashboard" />;
  const error = info.error || health.error || sources.error || foundation.error;
  if (error) return <ErrorState error={error} />;

  const systemWorking = health.data!.status === "healthy" && info.data!.database_health === "healthy";
  const sourceItems = sources.data!;
  const cards = [
    ["Catalog securities", foundation.data!.catalog_securities], ["Historical coverage", foundation.data!.historical_assets],
    ["Realtime active", foundation.data!.realtime_active], ["Operating mode", foundation.data!.operating_mode],
  ];
  return <section>
    <div className="page-heading"><div><p className="eyebrow">HOME</p><h1>Research dashboard</h1><p>Check automatically maintained market coverage, continue research, and review simulated results.</p></div></div>

    <div className={`status-banner ${systemWorking ? "ready" : "attention"}`} role="status">
      <div><strong>{systemWorking ? "System ready" : "System needs attention"}</strong><span>{systemWorking ? "The application and research database are working." : "Open System Status for details before starting new research."}</span></div>
      <Link to="/status">View system status</Link>
    </div>

    <div className="metric-grid">{cards.map(([label, value]) => <article className="metric" key={label}><span>{label}</span><strong>{value}</strong></article>)}</div>

    <h2 className="section-title">Continue your work</h2>
    <div className="quick-action-grid">{quickActions.map(action =>
      <Link className="quick-action" to={action.to} key={action.to}><strong>{action.title}</strong><span>{action.detail}</span><i aria-hidden="true">→</i></Link>
    )}</div>

    <div className="dashboard-grid">
      <article className="panel getting-started"><p className="eyebrow">NEXT STEPS</p><h2>Getting started</h2><ol>
        <li><Link to="/assets">Search the U.S. security catalog</Link><span>Start with canonical securities and explicit data capabilities.</span></li>
        <li><Link to="/watchlists">Create or open a watchlist</Link><span>Choose a manageable group of markets to follow.</span></li>
        <li><Link to="/strategies">Test a strategy with a backtest</Link><span>Use historical tests to challenge an idea—not prove future profits.</span></li>
        <li><Link to="/backtests">Review the results and assumptions</Link><span>Check costs, data coverage, and validation warnings.</span></li>
        <li><Link to="/paper-portfolios">Practice in a paper portfolio</Link><span>Use simulated money before considering real-world decisions.</span></li>
      </ol></article>

      <article className="panel"><div className="panel-title"><div><p className="eyebrow">MARKET DATA</p><h2>{foundation.data!.message}</h2></div><span className="health"><i />{foundation.data!.automatic_refresh}</span></div>
        <p>Coverage: {foundation.data!.historical_assets} assets · {foundation.data!.real_price_bars.toLocaleString()} real bars · {foundation.data!.realtime_active} realtime symbols.</p>
        {sourceItems.length ? sourceItems.map(source => <div className="source-row" key={source.id}><div><b>{source.name}</b><small>{source.last_successful_retrieval ? `Last refreshed ${new Date(source.last_successful_retrieval).toLocaleString()}` : "No successful refresh recorded"}</small></div><span className="data-state">{source.freshness_status}</span></div>) : <p className="muted">No market data sources are configured yet. Import market data to begin.</p>}
        <Link className="text-link" to="/data-sources">Review market data</Link>
      </article>
    </div>

    <div className="platform-note"><strong>Research and paper trading only.</strong> Market Intelligence Lab does not guarantee profits and does not automatically place real-money trades.</div>
  </section>;
}
