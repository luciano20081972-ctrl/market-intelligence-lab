import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router";
import { api } from "../api";
import { EmptyState, ErrorState, LoadingState } from "../components/States";

function value(item: Record<string, unknown>, key: string) {
  const result = item[key];
  return typeof result === "object" ? JSON.stringify(result) : String(result ?? "—");
}

export function ResearchMemoryPage() {
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["research-memory"], queryFn: api.researchMemory });
  const seed = useMutation({
    mutationFn: api.runResearchIntelligenceFixture,
    onSuccess: async () => { await queryClient.invalidateQueries(); },
  });
  if (query.isLoading) return <LoadingState label="Loading institutional research memory" />;
  if (query.error) return <ErrorState error={query.error} />;
  return <section><div className="page-heading"><div><p className="eyebrow">PERSISTENT INSTITUTIONAL MEMORY</p><h1>Research Memory</h1><p>Completed research remains searchable—including failed and contradicted work—without becoming a universal rule.</p></div><button onClick={() => seed.mutate()} disabled={seed.isPending}>{seed.isPending ? "Building…" : "Load reference research memory"}</button></div>
    <div className="disclaimer"><strong>Scientific boundary</strong><p>Historically validated does not guarantee a future result. Memory is not conversational AI memory or investment advice.</p></div>
    {!query.data?.items.length ? <EmptyState title="No research memory yet" detail="Complete validated or rejected research, or load the deterministic reference fixture." /> : <div className="source-grid">{query.data.items.map(item => <article className="panel" key={item.id}><p className="eyebrow">{item.conclusion === "POSITIVE" ? "WHAT WORKED?" : "WHAT FAILED?"}</p><h2>{item.company_name ?? item.feature_key}</h2><p><span className="status-chip">{item.status}</span> {item.feature_key}</p><p><strong>Where:</strong> {String(item.applicability.business_model ?? item.applicability.sector ?? "bounded applicability")}</p><p><strong>When:</strong> {new Date(item.first_learned_at).toLocaleDateString()}</p><p><strong>Why:</strong> {(item.failure_reasons[0] ?? item.success_conditions[0] ?? "See exact experiment evidence")}</p><Link to={`/research/memory/${item.id}`}>Inspect memory and applicability</Link></article>)}</div>}</section>;
}

export function ResearchMemoryDetail() {
  const { id = "" } = useParams();
  const query = useQuery({ queryKey: ["research-memory", id], queryFn: () => api.researchMemoryDetail(id), enabled: Boolean(id) });
  if (query.isLoading) return <LoadingState label="Loading memory evidence" />;
  if (query.error) return <ErrorState error={query.error} />;
  const item = query.data!;
  return <section><Link className="back-link" to="/research/memory">← Research Memory</Link><div className="page-heading"><div><p className="eyebrow">IMMUTABLE HISTORICAL LESSON</p><h1>{item.company_name ?? item.feature_key}</h1><p>{item.conclusion} · confidence {item.confidence} · {item.status}</p></div></div>
    <div className="metric-grid"><article className="panel"><h2>{item.conclusion}</h2><p>What happened?</p></article><article className="panel"><h2>{item.regime_context.join(" · ")}</h2><p>Regime context</p></article><article className="panel"><h2>{String(item.applicability.business_model ?? "Scoped")}</h2><p>Where it applies</p></article></div>
    <div className="two-column"><article className="panel"><h2>Applicability</h2><pre className="json-block">{JSON.stringify(item.applicability, null, 2)}</pre></article><article className="panel"><h2>Exact outcome attribution</h2><ul>{[...item.failure_reasons, ...item.success_conditions].map(reason => <li key={reason}>{reason}</li>)}</ul></article></div>
    <article className="panel"><h2>Memory-aware scheduling decisions</h2>{item.memory_decisions?.length ? item.memory_decisions.map((decision, index) => <div key={`${decision.classification}-${index}`}><strong>{decision.classification} → {decision.decision}</strong><p>{decision.reason}{decision.override_authorized ? " · authorized override audited" : ""}</p></div>) : <p>No equivalent proposal has been classified yet.</p>}</article></section>;
}

export function ResearchContradictionsPage() {
  const query = useQuery({ queryKey: ["research-contradictions"], queryFn: api.researchContradictions });
  if (query.isLoading) return <LoadingState label="Loading contradictions" />;
  if (query.error) return <ErrorState error={query.error} />;
  return <section><div className="page-heading"><div><p className="eyebrow">DO NOT AVERAGE AWAY DISAGREEMENT</p><h1>Research Contradictions</h1><p>Opposing findings remain visible across periods, regimes, universes, and business models.</p></div></div><div className="source-grid">{query.data?.items.map(item => <article className="panel" key={value(item, "id")}><h2>{value(item, "conflicting_dimension")}</h2><p>Confidence {value(item, "confidence")}</p><p>{value(item, "possible_explanations")}</p><small>Possible explanations are not causal proof.</small></article>)}</div></section>;
}

export function ResearchRegimeContextPage() {
  const query = useQuery({ queryKey: ["research-regimes"], queryFn: api.researchRegimes });
  if (query.isLoading) return <LoadingState label="Loading point-in-time regime context" />;
  if (query.error) return <ErrorState error={query.error} />;
  return <section><div className="page-heading"><div><p className="eyebrow">LIGHTWEIGHT · VERSIONED · POINT-IN-TIME</p><h1>Research Regime Context</h1><p>Deterministic thresholds describe historical context without a large ML regime classifier.</p></div></div>{query.data?.definitions.map(item => <article className="panel" key={value(item, "id")}><h2>{value(item, "label")}</h2><pre className="json-block">{JSON.stringify(item.method, null, 2)}</pre><p>{query.data.assignments.length} point-in-time assignments</p></article>)}</section>;
}

export function SignalIndependencePage() {
  const query = useQuery({ queryKey: ["signal-independence"], queryFn: api.signalIndependence });
  if (query.isLoading) return <LoadingState label="Loading signal independence analyses" />;
  if (query.error) return <ErrorState error={query.error} />;
  return <section><div className="page-heading"><div><p className="eyebrow">PREDICTIVE ≠ INDEPENDENT</p><h1>Signal Independence</h1><p>OOS predictive strength and unique contribution are measured separately against conventional information.</p></div></div><div className="source-grid">{query.data?.items.map(item => <article className="panel" key={item.id}><h2>{item.factor_key}</h2><div className="metric-grid"><div><strong>{item.predictive_strength}</strong><p>Predictive Strength</p></div><div><strong>{item.independent_contribution}</strong><p>Independent Contribution</p></div><div><strong>{item.redundancy_score}</strong><p>Redundancy</p></div></div><p>Independent Information Score: <strong>{item.independent_information_score}</strong></p><small>Independent does not mean causal or profitable.</small></article>)}</div></section>;
}

export function FactorRedundancyPage() {
  const redundancy = useQuery({ queryKey: ["factor-redundancy"], queryFn: api.factorRedundancy });
  if (redundancy.isLoading) return <LoadingState label="Loading factor redundancy matrix" />;
  if (redundancy.error) return <ErrorState error={redundancy.error} />;
  return <section><div className="page-heading"><div><p className="eyebrow">PAIRWISE + PARTIAL + RESIDUAL</p><h1>Factor Redundancy Matrix</h1><p>Correlation alone never declares two signals identical.</p></div></div><div className="table-wrap"><table><thead><tr><th>Factor</th><th>Compared with</th><th>Method</th><th>Result</th></tr></thead><tbody>{redundancy.data?.items.map(item => <tr key={value(item, "id")}><td>{value(item, "factor_a")}</td><td>{value(item, "factor_b")}</td><td>{value(item, "methodology")}</td><td>{value(item, "result")}</td></tr>)}</tbody></table></div></section>;
}

export function FactorClustersPage() {
  const query = useQuery({ queryKey: ["factor-clusters"], queryFn: api.factorClusters });
  if (query.isLoading) return <LoadingState label="Loading information families" />;
  if (query.error) return <ErrorState error={query.error} />;
  return <section><div className="page-heading"><div><p className="eyebrow">INFORMATION FAMILIES</p><h1>Factor Clusters</h1><p>Similarity groups expose redundancy; they do not prove causal structure.</p></div></div><div className="source-grid">{query.data?.items.map(item => <article className="panel" key={value(item, "id")}><h2>{value(item, "information_family")}</h2><p>{value(item, "members")}</p><small>Method: {value(item, "methodology")}</small></article>)}</div></section>;
}

export function DivergenceMonitorPage() {
  const query = useQuery({ queryKey: ["divergence-events"], queryFn: api.divergenceEvents });
  if (query.isLoading) return <LoadingState label="Loading cross-domain disagreement" />;
  if (query.error) return <ErrorState error={query.error} />;
  return <section><div className="page-heading"><div><p className="eyebrow">DIVERGENT ≠ MISPRICED</p><h1>Divergence Monitor</h1><p>Independent domains disagree enough to deserve research—not a BUY, SELL, or trading instruction.</p></div></div><div className="source-grid">{query.data?.items.map(item => <article className="panel" key={item.id}><h2>{item.company_name}</h2><p><span className="status-chip">{item.status}</span> magnitude {item.disagreement_magnitude}</p><p>{Object.entries(item.domain_values).map(([domain, domainValue]) => `${domain}: ${domainValue.normalized}`).join(" · ")}</p><p>Persistence: {item.persistence_periods} periods · evidence coverage {item.data_completeness}</p><Link to={`/research/divergence/${item.id}`}>Inspect divergence evidence</Link></article>)}</div></section>;
}

export function DivergenceDetailPage() {
  const { id = "" } = useParams();
  const query = useQuery({ queryKey: ["divergence-event", id], queryFn: () => api.divergenceEvent(id), enabled: Boolean(id) });
  if (query.isLoading) return <LoadingState label="Loading divergence evidence" />;
  if (query.error) return <ErrorState error={query.error} />;
  const item = query.data!;
  return <section><Link className="back-link" to="/research/divergence">← Divergence Monitor</Link><div className="page-heading"><div><p className="eyebrow">CROSS-DOMAIN RESEARCH CANDIDATE</p><h1>{item.company_name}</h1><p>{item.status} · priority {item.research_priority} · no paper eligibility</p></div></div><div className="two-column"><article className="panel"><h2>Domain evidence</h2><pre className="json-block">{JSON.stringify(item.domain_values, null, 2)}</pre></article><article className="panel"><h2>Magnitude decomposition</h2><pre className="json-block">{JSON.stringify(item.magnitude_components, null, 2)}</pre></article></div><article className="panel"><h2>Historical analogues</h2><pre className="json-block">{JSON.stringify(item.historical_analogues, null, 2)}</pre><p>Historical sample size is always shown; tiny samples imply no strength.</p></article><div className="disclaimer"><strong>Research-only workflow</strong><p>Divergence may create a Research Candidate. It cannot directly become PAPER_ELIGIBLE.</p></div></section>;
}

export function InformationValuePage() {
  const query = useQuery({ queryKey: ["information-value"], queryFn: api.informationValue });
  if (query.isLoading) return <LoadingState label="Loading research-resource efficiency" />;
  if (query.error) return <ErrorState error={query.error} />;
  return <section><div className="page-heading"><div><p className="eyebrow">RESEARCH RESOURCE EFFICIENCY · NOT INVESTMENT ROI</p><h1>Information Value</h1><p>Dataset use, unique contribution, redundancy, compute, storage, and sample size remain decomposed.</p></div></div><div className="source-grid">{query.data?.items.map(item => <article className="panel" key={value(item, "id")}><h2>{value(item, "resource_key")}</h2><p>{value(item, "metrics")}</p><p><strong>Evidence-based recommendation:</strong> {value(item, "recommendation")}</p><small>Sample size {value(item, "sample_size")}; no dataset is automatically disabled.</small></article>)}</div></section>;
}

export function ResearchMethodReliabilityPage() {
  const query = useQuery({ queryKey: ["method-reliability"], queryFn: api.researchMethodReliability });
  if (query.isLoading) return <LoadingState label="Loading research-method reliability" />;
  if (query.error) return <ErrorState error={query.error} />;
  return <section><div className="page-heading"><div><p className="eyebrow">SAMPLE-SIZE-AWARE METHOD EVIDENCE</p><h1>Research Method Reliability</h1><p>Origins are compared through evidence qualification, OOS survival, duplicates, rejections, and negative controls.</p></div></div><div className="source-grid">{query.data?.items.map(item => <article className="panel" key={value(item, "id")}><h2>{value(item, "method")}</h2><p>{value(item, "metrics")}</p><p>{value(item, "interpretation")}</p></article>)}</div></section>;
}
