import { NavLink, Outlet } from "react-router-dom";
import { DemoWarning } from "./States";

const links: Array<{ to: string; label: string }> = [
  { to: "/", label: "Overview" },
  { to: "/watchlists", label: "Watchlists" },
  { to: "/assets", label: "Asset Explorer" },
  { to: "/strategies", label: "Strategy Lab" },
  { to: "/backtests", label: "Backtests" },
  { to: "/paper-portfolios", label: "Paper Portfolios" },
  { to: "/data-sources", label: "Data Sources" },
  { to: "/status", label: "System Status" },
  { to: "/docs", label: "Documentation" },
];

export function Layout() {
  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><span className="brand-mark">MIL</span><div>Market Intelligence<small>Research Lab · v0.2.0</small></div></div>
      <nav aria-label="Primary navigation">
        {links.map(({ to, label }) => <NavLink key={to} to={to} end={to === "/"}>{label}</NavLink>)}
      </nav>
      <div className="sidebar-foot"><span className="status-dot" />Local research environment</div>
    </aside>
    <div className="main-column">
      <header className="topbar"><div><b>Research workspace</b><span>Simulation only</span></div><span className="version-chip">v0.2.0</span></header>
      <DemoWarning />
      <main><Outlet /></main>
    </div>
  </div>;
}
