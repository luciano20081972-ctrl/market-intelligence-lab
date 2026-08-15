import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "../api";
import { ErrorState, LoadingState } from "../components/States";

function Boundary() {
  return <div className="disclaimer"><strong>SIMULATED / PAPER ONLY</strong><p>Research forecasts are not investment advice. Historical replay is not prospective evidence, and paper performance is not real performance.</p></div>;
}

function Mode({ value }: { value: unknown }) {
  return <span className="version-chip">{String(value).replace("_", " ")}</span>;
}

export function ProspectiveForecastsPage() {
  const query = useQuery({ queryKey: ["prospective-forecasts"], queryFn: api.prospectiveForecasts });
  if (query.isLoading) return <LoadingState label="Loading frozen forecasts" />;
  if (query.isError) return <ErrorState error={query.error} />;
  return <section><div className="page-heading"><div><p className="eyebrow">FROZEN BEFORE OUTCOME</p><h1>Prospective Forecasts</h1><p>Point-in-time expectations remain immutable after lock and cannot be scored before maturity.</p></div></div><Boundary /><div className="metric-grid"><article className="panel"><h2>Evaluation populations</h2><p><Mode value="PROSPECTIVE" /> <Mode value="HISTORICAL REPLAY" /> <Mode value="FIXTURE" /></p><p>These populations are always calculated separately.</p></article><article className="panel"><h2>Forecast ledger</h2><strong>{query.data?.items.length ?? 0}</strong><p>frozen or open research forecasts</p></article></div>{query.data?.items.map(item => <article className="panel" key={String(item.id)}><h2>{String(item.forecast_type)}</h2><p><Mode value={item.evaluation_mode} /> <Mode value={item.state} /></p><p>Outcome eligible: {String(item.outcome_eligible_time)}</p><small>Checksum {String(item.checksum).slice(0, 12)}…</small></article>)}</section>;
}

export function OutcomeMonitorPage() {
  const query = useQuery({ queryKey: ["forecast-outcomes"], queryFn: api.forecastOutcomes });
  return <section><p className="eyebrow">TEMPORAL TRUTH</p><h1>Outcome Monitor</h1><Boundary />{query.isLoading ? <LoadingState label="Loading outcomes" /> : query.isError ? <ErrorState error={query.error} /> : <><p>{query.data?.items.length ?? 0} immutable observations. Early outcomes are rejected.</p><pre className="json-block">{JSON.stringify(query.data?.items, null, 2)}</pre></> }</section>;
}

export function CalibrationPage({ confidence = false }: { confidence?: boolean }) {
  const query = useQuery({ queryKey: ["calibration", confidence], queryFn: confidence ? api.confidenceCalibration : api.forecastCalibration });
  return <section><p className="eyebrow">EMPIRICAL · SAMPLE SIZE VISIBLE</p><h1>{confidence ? "Confidence Calibration" : "Forecast Calibration"}</h1><Boundary />{query.isLoading ? <LoadingState label="Loading calibration" /> : query.isError ? <ErrorState error={query.error} /> : <div className="metric-grid"><article className="panel"><h2>{String(query.data?.status)}</h2><strong>{String(query.data?.sample_count)}</strong><p>prospective observations</p></article><article className="panel"><h2>Scientific boundary</h2><p>Research confidence is a decomposition, not an event probability.</p></article></div>}</section>;
}

export function ReliabilityPage() {
  const query = useQuery({ queryKey: ["reliability"], queryFn: api.researchReliabilityV13 });
  return <section><p className="eyebrow">VERSIONED FEEDBACK</p><h1>Research Reliability</h1><Boundary />{query.isLoading ? <LoadingState label="Loading reliability" /> : query.isError ? <ErrorState error={query.error} /> : <pre className="json-block">{JSON.stringify(query.data?.items, null, 2)}</pre>}</section>;
}

export function FeedbackPage() {
  const query = useQuery({ queryKey: ["feedback"], queryFn: api.feedbackRecommendations });
  return <section><p className="eyebrow">HUMAN APPROVAL REQUIRED</p><h1>Feedback Recommendations</h1><p>Recommendations never rewrite algorithms or research policy automatically.</p>{query.isLoading ? <LoadingState label="Loading recommendations" /> : query.isError ? <ErrorState error={query.error} /> : <pre className="json-block">{JSON.stringify(query.data?.items, null, 2)}</pre>}</section>;
}

export function PaperPortfolioLabPage() {
  const candidates = useQuery({ queryKey: ["paper-candidates-v13"], queryFn: api.paperAllocationCandidates });
  const preview = useMutation({ mutationFn: api.previewPaperPlan });
  return <section><div className="page-heading"><div><p className="eyebrow">SIMULATED / PAPER ONLY</p><h1>Paper Portfolio Lab</h1><p>Qualified research enters deterministic eligibility, portfolio, risk, scenario, and preview gates—never a broker.</p></div><button onClick={() => preview.mutate()} disabled={preview.isPending}>Preview reference plan</button></div><Boundary /><div className="metric-grid"><article className="panel"><h2>Allocation Candidates</h2><strong>{candidates.data?.items.length ?? 0}</strong><p>Uncalibrated candidates use stricter risk limits.</p></article><article className="panel"><h2>Risk Review</h2><p>No shorting · no leverage · optimizer subordinate to hard risk.</p></article><article className="panel"><h2>Scenario Stress</h2><p>No scenario probabilities are invented.</p></article></div>{preview.data && <><h2>Rebalance Preview</h2><pre className="json-block">{JSON.stringify(preview.data, null, 2)}</pre></>}</section>;
}

export function PaperPerformancePage() {
  const query = useQuery({ queryKey: ["paper-evaluation-v13"], queryFn: api.paperEvaluationV13 });
  return <section><p className="eyebrow">SIMULATED / PAPER ONLY</p><h1>Paper Performance</h1><Boundary />{query.isLoading ? <LoadingState label="Loading simulated performance" /> : query.isError ? <ErrorState error={query.error} /> : <pre className="json-block">{JSON.stringify(query.data, null, 2)}</pre>}</section>;
}

export function PortfolioAttributionPage() {
  const query = useQuery({ queryKey: ["paper-attribution-v13"], queryFn: api.paperAttributionV13 });
  return <section><p className="eyebrow">CONTRIBUTION, NOT CAUSALITY</p><h1>Portfolio Attribution</h1><Boundary />{query.isLoading ? <LoadingState label="Loading attribution" /> : query.isError ? <ErrorState error={query.error} /> : <pre className="json-block">{JSON.stringify(query.data, null, 2)}</pre>}</section>;
}
