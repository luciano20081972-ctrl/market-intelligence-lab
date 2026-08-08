import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router";
import { api } from "../api";
import { EmptyState, ErrorState, LoadingState } from "../components/States";

const levels = ["LEVEL_0", "LEVEL_1", "LEVEL_2", "LEVEL_3", "LEVEL_4"];
const labels: Record<string, string> = {
  LEVEL_0: "Universe",
  LEVEL_1: "Cheap Screen",
  LEVEL_2: "Structured",
  LEVEL_3: "Domain Deep Dive",
  LEVEL_4: "AI Candidates",
};

export function ResearchUniversePage() {
  const query = useQuery({ queryKey: ["research-universes"], queryFn: api.researchUniverses });
  if (query.isLoading) return <LoadingState label="Loading point-in-time universes" />;
  if (query.error) return <ErrorState error={query.error} />;
  return <section><div className="page-heading"><div><p className="eyebrow">POINT-IN-TIME MEMBERSHIP</p><h1>Research Universe</h1><p>Historical screens use the constituent version eligible at the requested time.</p></div></div>
    {!query.data?.items.length ? <EmptyState title="No research universe" detail="Run the deterministic reference screening fixture." /> : null}
    <div className="source-grid">{query.data?.items.map((item) => <article className="panel" key={item.id}><h2>{item.name}</h2><p>{item.description}</p><p><span className="version-chip">{item.owner_type}</span> {item.source}</p></article>)}</div></section>;
}

export function FeatureCatalog() {
  const query = useQuery({ queryKey: ["research-features"], queryFn: api.researchFeatures });
  if (query.isLoading) return <LoadingState label="Loading feature catalog" />;
  if (query.error) return <ErrorState error={query.error} />;
  return <section><div className="page-heading"><div><p className="eyebrow">MEASUREMENTS, NOT ALPHA</p><h1>Feature Catalog</h1><p>Versioned definitions with temporal, lineage, normalization, and cost policies.</p></div></div>
    <div className="table-wrap"><table><thead><tr><th>Feature</th><th>Domain</th><th>Entity</th><th>Status</th></tr></thead><tbody>{query.data?.items.map((item) => <tr key={item.id}><td><b>{item.name}</b><br /><small>{item.feature_key}</small></td><td>{item.domain}</td><td>{item.entity_type}</td><td><span className="version-chip">{item.status}</span></td></tr>)}</tbody></table></div></section>;
}

export function FeatureExplorer() {
  const query = useQuery({ queryKey: ["feature-values"], queryFn: api.featureValues });
  if (query.isLoading) return <LoadingState label="Building point-in-time matrix" />;
  if (query.error) return <ErrorState error={query.error} />;
  return <section><div className="page-heading"><div><p className="eyebrow">AS-OF MATRIX</p><h1>Point-in-Time Feature Matrix</h1><p>Only values with simulation eligibility at or before the research cutoff are visible.</p></div></div>
    <p><span className="version-chip">{query.data?.point_in_time_safe ? "POINT-IN-TIME SAFE" : "UNSAFE"}</span></p>
    <div className="table-wrap"><table><thead><tr><th>Feature</th><th>Entity</th><th>Value</th><th>Eligible</th><th>Quality</th><th>Lineage</th></tr></thead><tbody>{query.data?.items.slice(0, 100).map((item) => <tr key={item.id}><td>{item.feature_key}</td><td>{item.entity_id.slice(0, 8)}</td><td>{item.value} {item.unit}</td><td>{new Date(item.simulation_eligible_time).toLocaleDateString()}</td><td>{item.quality_state}</td><td><Link to={`/research/lineage/${item.id}`}>Trace</Link></td></tr>)}</tbody></table></div></section>;
}

export function ResearchFunnel() {
  const client = useQueryClient();
  const query = useQuery({ queryKey: ["screening-runs"], queryFn: api.screeningRuns });
  const run = useMutation({ mutationFn: api.runReferenceScreening, onSuccess: async () => { await client.invalidateQueries({ queryKey: ["screening-runs"] }); } });
  const latest = query.data?.items[0];
  return <section><div className="page-heading"><div><p className="eyebrow">PROGRESSIVE RESOLUTION</p><h1>Research Funnel</h1><p>Transparent research prioritization constrained by data and compute budgets—not an investment recommendation.</p></div><button onClick={() => run.mutate()} disabled={run.isPending}>{run.isPending ? "Running…" : "Run reference screen"}</button></div>
    {query.error ? <ErrorState error={query.error} /> : null}{query.isLoading ? <LoadingState label="Loading screening runs" /> : null}
    {latest ? <><div className="research-funnel">{levels.map((level, index) => <div key={level}><article className="panel"><p className="eyebrow">{level}</p><h2>{latest.funnel[level]}</h2><p>{labels[level]}</p></article>{index < levels.length - 1 ? <span aria-hidden="true">↓</span> : null}</div>)}</div>
      <p><Link to={`/research/screening-runs/${latest.id}`}>Inspect screening decisions and reason codes</Link></p></> : <EmptyState title="No screening run" detail="Run the deterministic 100-company fixture." />}</section>;
}

export function ScreeningRunDetail() {
  const { id = "" } = useParams();
  const query = useQuery({ queryKey: ["screening-run", id], queryFn: () => api.screeningRun(id), enabled: Boolean(id) });
  if (query.isLoading) return <LoadingState label="Loading screening decision evidence" />;
  if (query.error) return <ErrorState error={query.error} />;
  return <section><Link className="back-link" to="/research/funnel">← Research Funnel</Link><div className="page-heading"><div><p className="eyebrow">REPRODUCIBLE RUN</p><h1>Screening Run Detail</h1><p>Checksum {query.data?.checksum.slice(0, 16)} · as of {query.data && new Date(query.data.as_of_time).toLocaleString()}</p></div></div>
    <div className="table-wrap"><table><thead><tr><th>Entity</th><th>Level</th><th>Score</th><th>Decision</th><th>Reasons</th></tr></thead><tbody>{query.data?.decisions.slice(0, 100).map((item) => <tr key={item.id}><td>{item.entity_id.slice(0, 8)}</td><td>{item.level}</td><td>{item.score}</td><td>{item.recommendation}</td><td>{item.reason_codes.join(", ")}</td></tr>)}</tbody></table></div></section>;
}

export function ResearchCandidateDetail() {
  const { id = "" } = useParams();
  const candidates = useQuery({ queryKey: ["research-candidates"], queryFn: api.researchCandidates, enabled: !id });
  const detail = useQuery({ queryKey: ["research-candidate", id], queryFn: () => api.researchCandidate(id), enabled: Boolean(id) });
  if (candidates.isLoading || detail.isLoading) return <LoadingState label="Loading research candidates" />;
  const error = candidates.error ?? detail.error;
  if (error) return <ErrorState error={error} />;
  if (!id) return <section><div className="page-heading"><div><p className="eyebrow">DEEPER RESEARCH ELIGIBILITY</p><h1>Research Candidates</h1><p>Priority state is not alpha, expected return, buy, or sell advice.</p></div></div><div className="source-grid">{candidates.data?.items.slice(0, 20).map((item) => <article className="panel" key={item.id}><h2>{item.company_name}</h2><p>{item.archetype} · <span className="version-chip">{item.current_level}</span></p><Link to={`/research/candidates/${item.id}`}>Inspect rationale</Link></article>)}</div></section>;
  const item = detail.data;
  return <section><Link className="back-link" to="/research/candidates">← Candidates</Link><div className="page-heading"><div><p className="eyebrow">CANDIDATE DETAIL</p><h1>{item?.company_name}</h1><p>{item?.promotion_reason}</p></div></div><div className="metric-grid"><article className="panel"><h2>{item?.current_level}</h2><p>Research resolution</p></article><article className="panel"><h2>{item?.archetype}</h2><p>Reference driver profile</p></article><article className="panel"><h2>{item?.irrelevant_pipelines_skipped ? "Yes" : "No"}</h2><p>Irrelevant pipelines skipped</p></article></div><article className="panel"><h2>Selected data pipelines</h2><p>{item?.selected_pipelines?.join(" · ")}</p></article></section>;
}

export function ResearchBudgetDashboard() {
  const query = useQuery({ queryKey: ["research-budgets"], queryFn: api.researchBudgets });
  if (query.isLoading) return <LoadingState label="Loading research budgets" />;
  if (query.error) return <ErrorState error={query.error} />;
  return <section><div className="page-heading"><div><p className="eyebrow">PRE-EXECUTION CONTROL</p><h1>Research Budget Dashboard</h1><p>Population, request, byte, storage, CPU, placeholder-token, and concurrency limits.</p></div></div><div className="source-grid">{query.data?.items.map((item) => <article className="panel" key={item.id}><p className="eyebrow">{item.level}</p><h2>{item.cost_class}</h2><p>Maximum companies: {item.limits.maximum_companies}</p><p>CPU seconds: {item.limits.cpu_seconds}</p><p>API requests/company: {item.limits.api_requests_per_company}</p></article>)}</div></section>;
}

export function FeatureLineageViewer() {
  const { id = "" } = useParams();
  const query = useQuery({ queryKey: ["feature-lineage", id], queryFn: () => api.featureLineage(id), enabled: Boolean(id) });
  if (query.isLoading) return <LoadingState label="Tracing feature lineage" />;
  if (query.error) return <ErrorState error={query.error} />;
  return <section><Link className="back-link" to="/research/features/explorer">← Feature Matrix</Link><div className="page-heading"><div><p className="eyebrow">REPRODUCIBLE PROVENANCE</p><h1>Feature Lineage Viewer</h1><p>Feature value → observations/manifests → graph/evidence → computation version.</p></div></div><article className="panel"><pre>{JSON.stringify(query.data, null, 2)}</pre></article></section>;
}
