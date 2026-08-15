import { NavLink, Outlet, useLocation } from "react-router";
import { useAuth } from "../auth";
import { DemoWarning } from "./States";

interface NavigationLink {
  to: string;
  label: string;
  description?: string;
}

interface NavigationSection {
  label: string;
  links: NavigationLink[];
}

const primarySections: NavigationSection[] = [
  { label: "Home", links: [{ to: "/", label: "Dashboard", description: "System health, data status, and next steps" }] },
  { label: "Research", links: [
    { to: "/watchlists", label: "Watchlists", description: "Keep the companies and funds you follow in one place" },
    { to: "/assets", label: "Market Research", description: "Explore market history and available assets" },
    { to: "/sec", label: "Company Filings & Activity", description: "Review SEC filings, ownership, and company disclosures" },
    { to: "/research/hypotheses", label: "Factor Research", description: "Test economic ideas with controlled historical experiments" },
  ] },
  { label: "Test Strategies", links: [
    { to: "/strategies", label: "Strategy Lab", description: "Choose assumptions and prepare a historical test" },
    { to: "/backtests", label: "Backtest Results", description: "Review completed historical strategy tests" },
    { to: "/optimization", label: "Strategy Optimization", description: "Compare constrained strategy configurations" },
  ] },
  { label: "Paper Trading", links: [
    { to: "/paper-portfolios", label: "Paper Portfolios", description: "Review simulated portfolios, orders, and performance" },
    { to: "/paper/lab", label: "Paper Portfolio Lab", description: "Build risk-reviewed simulated plans from qualified research" },
    { to: "/paper/performance", label: "Paper Performance", description: "Evaluate simulated outcomes separately from forecast quality" },
  ] },
  { label: "Data", links: [
    { to: "/data-sources", label: "Market Data", description: "See available data and when it was last refreshed" },
    { to: "/imports", label: "Import Market Data", description: "Refresh or add historical market data" },
    { to: "/providers", label: "Data Provider Status", description: "Check whether connected data providers are working" },
    { to: "/corporate-actions", label: "Corporate Actions", description: "Review splits, dividends, and symbol changes" },
    { to: "/data-quality", label: "Data Quality", description: "Review missing, stale, or conflicting records" },
    { to: "/exchange-calendar", label: "Market Events Calendar", description: "Closures and events that can affect historical results" },
  ] },
];

const advancedSections: NavigationSection[] = [
  { label: "Advanced research", links: [
    { to: "/world-data", label: "Official Data Sources" },
    { to: "/world-data/manifests", label: "Data History & Provenance" },
    { to: "/world-data/macro", label: "Economic Data & Revisions" },
    { to: "/world-data/energy", label: "Energy Data Pilot" },
    { to: "/economic-graph", label: "Economic Relationships" },
    { to: "/driver-profiles", label: "Company Drivers" },
    { to: "/relationship-evidence", label: "Relationship Evidence" },
    { to: "/data-relevance", label: "Data Relevance" },
    { to: "/entity-resolution", label: "Entity Matching Review" },
    { to: "/research/universe", label: "Research Universe" },
    { to: "/research/features", label: "Research Measurements" },
    { to: "/research/features/explorer", label: "Feature Matrix" },
    { to: "/research/funnel", label: "Research Funnel" },
    { to: "/research/candidates", label: "Research Candidates" },
    { to: "/research/budgets", label: "Research Limits" },
    { to: "/research/engines", label: "Research Engine Status" },
    { to: "/research/memory", label: "Research Memory" },
    { to: "/research/contradictions", label: "Research Contradictions" },
    { to: "/research/regimes", label: "Research Regime Context" },
    { to: "/research/signal-independence", label: "Signal Independence" },
    { to: "/research/factor-redundancy", label: "Factor Redundancy" },
    { to: "/research/factor-clusters", label: "Factor Clusters" },
    { to: "/research/divergence", label: "Divergence Monitor" },
    { to: "/research/information-value", label: "Information Value" },
    { to: "/research/method-reliability", label: "Research Method Reliability" },
    { to: "/research/skeptic", label: "Adversarial Review" },
    { to: "/research/skeptic/challenges", label: "Skeptic Challenges" },
    { to: "/research/scenarios", label: "Scenario Lab" },
    { to: "/research/counterfactuals", label: "Counterfactual Lab" },
    { to: "/research/confidence", label: "Research Confidence" },
    { to: "/research/dossiers", label: "Research Dossiers" },
    { to: "/research/forecasts", label: "Prospective Forecasts" },
    { to: "/research/outcomes", label: "Outcome Monitor" },
    { to: "/research/calibration", label: "Forecast Calibration" },
    { to: "/research/calibration/confidence", label: "Confidence Calibration" },
    { to: "/research/reliability", label: "Research Reliability" },
    { to: "/research/feedback", label: "Feedback Recommendations" },
    { to: "/paper/attribution", label: "Portfolio Attribution" },
  ] },
  { label: "Data operations", links: [
    { to: "/operations", label: "Background Jobs" },
    { to: "/schedules", label: "Import Schedules" },
    { to: "/reconciliation", label: "Data Reconciliation" },
    { to: "/provider-comparisons", label: "Provider Comparison" },
  ] },
  { label: "Administration", links: [
    { to: "/status", label: "System Status" },
    { to: "/infrastructure", label: "System Services" },
    { to: "/upstream", label: "Data Providers & Integrations" },
    { to: "/analytics", label: "Analytics Comparison" },
    { to: "/workspace", label: "Workspace Settings" },
    { to: "/profile", label: "Profile" },
    { to: "/audit", label: "Activity Log" },
    { to: "/docs", label: "Documentation" },
  ] },
];

function NavigationLinks({ section }: { section: NavigationSection }) {
  return <div className="nav-section">
    <span className="nav-heading">{section.label}</span>
    {section.links.map(({ to, label, description }) =>
      <NavLink key={to} to={to} end={to === "/"} title={description}>{label}</NavLink>
    )}
  </div>;
}

export function Layout() {
  const auth = useAuth();
  const location = useLocation();
  const advancedRouteActive = advancedSections.some(section =>
    section.links.some(link => location.pathname === link.to || location.pathname.startsWith(`${link.to}/`))
  );
  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand">
        <picture>
          <source media="(max-width: 600px)" srcSet="/assets/branding/market-intelligence-lab-app-icon-256.png" />
          <img className="brand-logo" src="/assets/branding/market-intelligence-lab-logo-512.webp" alt="Market Intelligence Lab" />
        </picture>
        <div>Market Intelligence Lab<small>Prospective calibration · paper-only intelligence · v0.13.0</small></div>
      </div>
      <nav aria-label="Primary navigation">
        {primarySections.map(section => <NavigationLinks key={section.label} section={section} />)}
        <details className="advanced-nav" open={advancedRouteActive ? true : undefined}>
          <summary>More & administration</summary>
          <p>Technical, operational, and rarely used tools</p>
          {advancedSections.map(section => <NavigationLinks key={section.label} section={section} />)}
        </details>
      </nav>
      <div className="sidebar-foot"><span className="status-dot" />Private research environment</div>
    </aside>
    <div className="main-column">
      <header className="topbar"><div><b>{auth.workspace?.name ?? "Research workspace"}</b><span>Simulation only · {auth.workspace?.role}</span></div>
        <select aria-label="Workspace" value={auth.workspace?.id ?? ""} onChange={(event) => auth.switchWorkspace(event.target.value)}>{auth.workspaces.map((workspace) => <option key={workspace.id} value={workspace.id}>{workspace.name}</option>)}</select>
        <button onClick={() => void auth.signOut()}>Sign out</button><span className="version-chip">v0.13.0</span></header>
      <DemoWarning />
      <main><Outlet /></main>
    </div>
  </div>;
}
