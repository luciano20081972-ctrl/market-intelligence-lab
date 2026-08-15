import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router";
import { api } from "../api";
import { ErrorState, LoadingState } from "../components/States";

function Field({ label, value }: { label: string; value: unknown }) {
  return <div><strong>{label}</strong><p>{typeof value === "string" ? value : JSON.stringify(value)}</p></div>;
}

export function AdversarialReviewPage() {
  const client = useQueryClient();
  const query = useQuery({ queryKey: ["skeptic-reviews"], queryFn: api.skepticReviews });
  const seed = useMutation({ mutationFn: api.runAdversarialFixture, onSuccess: () => client.invalidateQueries({ queryKey: ["skeptic-reviews"] }) });
  if (query.isLoading) return <LoadingState label="Loading adversarial reviews" />;
  if (query.isError) return <ErrorState error={query.error} />;
  return <section><div className="page-heading"><div><p className="eyebrow">WHAT COULD BE WRONG?</p><h1>Adversarial Review</h1><p>Deterministic safeguards attack research conclusions before promotion.</p></div><button onClick={() => seed.mutate()} disabled={seed.isPending}>{seed.isPending ? "Building…" : "Load adversarial reference cases"}</button></div><div className="disclaimer"><strong>Scientific boundary</strong><p>Validated does not mean true. Review status is not a probability of profit.</p></div><div className="source-grid">{query.data?.items.map(item => <article className="panel" key={String(item.id)}><h2>{String(item.status)}</h2><Field label="Policy" value={item.policy_version} /><Link to={`/research/skeptic/reviews/${String(item.id)}`}>Inspect review</Link></article>)}</div></section>;
}

export function SkepticChallengesPage() {
  const query = useQuery({ queryKey: ["skeptic-challenges"], queryFn: api.skepticChallenges });
  if (query.isLoading) return <LoadingState label="Loading skeptic challenges" />;
  if (query.isError) return <ErrorState error={query.error} />;
  return <section><div className="page-heading"><div><p className="eyebrow">STRUCTURED RED TEAM</p><h1>Skeptic Challenges</h1><p>Every challenge exposes what could be wrong, severity, evidence, test, status, and resolution.</p></div></div>{query.data?.items.map(item => <article className="panel" key={String(item.id)}><h2>{String(item.title)}</h2><div className="metric-grid"><Field label="SEVERITY" value={item.severity} /><Field label="STATUS" value={item.status} /></div><Field label="EVIDENCE" value={item.evidence} /><Field label="TEST" value={item.proposed_test} /><Field label="RESOLUTION" value={item.resolution} /></article>)}</section>;
}

export function ChallengeDetailPage() {
  const { id } = useParams();
  const query = useQuery({ queryKey: ["skeptic-review", id], queryFn: () => api.skepticReview(id!), enabled: Boolean(id) });
  if (query.isLoading) return <LoadingState label="Loading challenge detail" />;
  if (query.isError) return <ErrorState error={query.error} />;
  return <section><Link className="back-link" to="/research/skeptic/challenges">← Skeptic Challenges</Link><h1>Challenge Detail</h1><pre className="json-block">{JSON.stringify(query.data, null, 2)}</pre></section>;
}

export function ResearchConfidencePage() {
  const query = useQuery({ queryKey: ["research-confidence"], queryFn: api.researchConfidence });
  return <section><div className="page-heading"><div><p className="eyebrow">TRANSPARENT DECOMPOSITION</p><h1>Research Confidence</h1><p>This profile is not a probability and never predicts profit.</p></div></div>{query.isLoading ? <LoadingState label="Loading confidence components" /> : query.isError ? <ErrorState error={query.error} /> : query.data?.items.map(item => <article className="panel" key={String(item.id)}><h2>{String(item.classification)}</h2><pre className="json-block">{JSON.stringify(item.components, null, 2)}</pre><Field label="Formula" value={item.formula_version} /></article>)}</section>;
}

export function ScenarioLabPage() {
  const query = useQuery({ queryKey: ["scenarios"], queryFn: api.scenarios });
  return <section><div className="page-heading"><div><p className="eyebrow">THIS IS A SCENARIO, NOT A FORECAST</p><h1>Scenario Lab</h1><p>Explore bounded hypothetical world states through supported transmission paths.</p></div></div>{query.isLoading ? <LoadingState label="Loading scenarios" /> : query.isError ? <ErrorState error={query.error} /> : <div className="source-grid">{query.data?.items.map(item => <article className="panel" key={String(item.id)}><h2>{String(item.title)}</h2><p>{String(item.description)}</p><p>{String(item.scenario_type)} · {String(item.plausibility)} plausibility</p><Link to={`/research/scenarios/${String(item.id)}`}>Inspect scenario</Link></article>)}</div>}</section>;
}

export function ScenarioDetailPage() {
  const { id } = useParams();
  const query = useQuery({ queryKey: ["scenario", id], queryFn: () => api.scenario(id!), enabled: Boolean(id) });
  const run = useMutation({ mutationFn: () => api.runScenario(id!) });
  if (query.isLoading) return <LoadingState label="Loading scenario" />;
  if (query.isError) return <ErrorState error={query.error} />;
  return <section><Link className="back-link" to="/research/scenarios">← Scenario Lab</Link><p className="eyebrow">THIS IS A SCENARIO, NOT A FORECAST</p><h1>{String(query.data?.title)}</h1><button onClick={() => run.mutate()} disabled={run.isPending}>Run deterministic scenario</button><h2>Transmission path and impact</h2><pre className="json-block">{JSON.stringify(run.data ?? query.data, null, 2)}</pre></section>;
}

export function ScenarioComparisonPage() {
  return <section><p className="eyebrow">NO FAVORABLE-CASE SELECTION</p><h1>Scenario Comparison</h1><p>Compare all defined sensitivity points, including adverse, threshold, saturated, and unstable responses.</p></section>;
}

export function CounterfactualLabPage() {
  const query = useQuery({ queryKey: ["counterfactuals"], queryFn: api.counterfactuals });
  return <section><div className="page-heading"><div><p className="eyebrow">THIS IS A SIMULATED ALTERNATIVE STATE, NOT PROVEN CAUSAL EFFECT</p><h1>Counterfactual Lab</h1><p>Isolated interventions test mechanism dependence without changing canonical evidence.</p></div></div>{query.isLoading ? <LoadingState label="Loading counterfactuals" /> : query.isError ? <ErrorState error={query.error} /> : query.data?.items.map(item => <article className="panel" key={String(item.id)}><h2>{String(item.title)}</h2><p>{String(item.identification_status)}</p><Link to={`/research/counterfactuals/${String(item.id)}`}>Inspect counterfactual</Link></article>)}</section>;
}

export function CounterfactualDetailPage() {
  const { id } = useParams();
  const query = useQuery({ queryKey: ["counterfactual", id], queryFn: () => api.counterfactual(id!), enabled: Boolean(id) });
  const run = useMutation({ mutationFn: () => api.runCounterfactual(id!) });
  if (query.isLoading) return <LoadingState label="Loading counterfactual" />;
  if (query.isError) return <ErrorState error={query.error} />;
  return <section><Link className="back-link" to="/research/counterfactuals">← Counterfactual Lab</Link><p className="eyebrow">THIS IS A SIMULATED ALTERNATIVE STATE, NOT PROVEN CAUSAL EFFECT</p><h1>{String(query.data?.title)}</h1><button onClick={() => run.mutate()} disabled={run.isPending}>Run isolated counterfactual</button><pre className="json-block">{JSON.stringify(run.data ?? query.data, null, 2)}</pre></section>;
}

export function ResearchDossierPage() {
  const query = useQuery({ queryKey: ["research-dossiers"], queryFn: api.researchDossiers });
  return <section><div className="page-heading"><div><p className="eyebrow">TRACEABLE RESEARCH PACKAGE</p><h1>Research Dossier</h1><p>Evidence, contradictions, assumptions, scenarios, counterfactuals, and falsification conditions—never a BUY/SELL recommendation.</p></div></div>{query.isLoading ? <LoadingState label="Loading dossiers" /> : query.isError ? <ErrorState error={query.error} /> : query.data?.items.map(item => <article className="panel" key={String(item.id)}><h2>{String(item.title)}</h2><Link to={`/research/dossiers/${String(item.id)}`}>Open dossier</Link></article>)}</section>;
}

export function ResearchDossierDetailPage() {
  const { id } = useParams();
  const query = useQuery({ queryKey: ["research-dossier", id], queryFn: () => api.researchDossier(id!), enabled: Boolean(id) });
  if (query.isLoading) return <LoadingState label="Loading dossier" />;
  if (query.isError) return <ErrorState error={query.error} />;
  return <section><Link className="back-link" to="/research/dossiers">← Research Dossiers</Link><h1>{String(query.data?.title)}</h1><pre className="json-block">{JSON.stringify(query.data?.sections, null, 2)}</pre><div className="disclaimer">No investment recommendation. Every conclusion must remain traceable to evidence.</div></section>;
}
