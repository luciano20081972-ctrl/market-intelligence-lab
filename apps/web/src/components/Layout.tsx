import { NavLink, Outlet } from "react-router-dom";
import { DemoWarning } from "./States";
import { useAuth } from "../auth";

const links: Array<{ to: string; label: string }> = [
  { to: "/", label: "Overview" },
  { to: "/watchlists", label: "Watchlists" },
  { to: "/assets", label: "Asset Explorer" },
  { to: "/strategies", label: "Strategy Lab" },
  { to: "/backtests", label: "Backtests" },
  { to: "/paper-portfolios", label: "Paper Portfolios" },
  { to: "/data-sources", label: "Data Sources" },
  { to: "/providers", label: "Providers" },
  { to: "/imports", label: "Import Jobs" },
  { to: "/operations", label: "Queue & Workers" },
  { to: "/schedules", label: "Schedules" },
  { to: "/reconciliation", label: "Reconciliation" },
  { to: "/provider-comparisons", label: "Provider Comparison" },
  { to: "/infrastructure", label: "Infrastructure" },
  { to: "/audit", label: "Audit Log" },
  { to: "/workspace", label: "Workspace Settings" },
  { to: "/profile", label: "Profile" },
  { to: "/data-quality", label: "Data Quality" },
  { to: "/corporate-actions", label: "Corporate Actions" },
  { to: "/exchange-calendar", label: "Exchange Calendar" },
  { to: "/status", label: "System Status" },
  { to: "/docs", label: "Documentation" },
];

export function Layout() {
  const auth = useAuth();
  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><span className="brand-mark">MIL</span><div>Market Intelligence<small>Research Lab · v0.5.0</small></div></div>
      <nav aria-label="Primary navigation">
        {links.map(({ to, label }) => <NavLink key={to} to={to} end={to === "/"}>{label}</NavLink>)}
      </nav>
      <div className="sidebar-foot"><span className="status-dot" />Local research environment</div>
    </aside>
    <div className="main-column">
      <header className="topbar"><div><b>{auth.workspace?.name ?? "Research workspace"}</b><span>Simulation only · {auth.workspace?.role}</span></div>
        <select aria-label="Workspace" value={auth.workspace?.id ?? ""} onChange={(event) => auth.switchWorkspace(event.target.value)}>{auth.workspaces.map((workspace) => <option key={workspace.id} value={workspace.id}>{workspace.name}</option>)}</select>
        <button onClick={() => void auth.signOut()}>Sign out</button><span className="version-chip">v0.5.0</span></header>
      <DemoWarning />
      <main><Outlet /></main>
    </div>
  </div>;
}
