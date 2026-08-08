import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router";
import { api } from "../api";
import { EmptyState, ErrorState, LoadingState } from "../components/States";

const partitionLabel = (value: string) => new Date(value).toLocaleDateString();

export function HypothesisLab() {
  const client = useQueryClient();
  const query = useQuery({ queryKey: ["hypotheses"], queryFn: api.hypotheses });
  const generate = useMutation({
    mutationFn: api.runHypothesisFixture,
    onSuccess: async () => {
      await Promise.all([
        client.invalidateQueries({ queryKey: ["hypotheses"] }),
        client.invalidateQueries({ queryKey: ["factor-experiments"] }),
      ]);
    },
  });
  if (query.isLoading) return <LoadingState label="Loading bounded research hypotheses" />;
  if (query.error) return <ErrorState error={query.error} />;
  return <section><div className="page-heading"><div><p className="eyebrow">SCIENTIFIC RESEARCH · NOT PREDICTION</p><h1>Hypothesis Lab</h1><p>Ideas become falsifiable economic mechanisms, declarative features, sealed experiments, and accepted or rejected research.</p></div><button onClick={() => generate.mutate()} disabled={generate.isPending}>{generate.isPending ? "Generating…" : "Generate fixture hypotheses"}</button></div>
    <div className="disclaimer"><strong>High rejection is healthy</strong><p>An LLM-generated idea is not a signal. Apparent universal success indicates leakage, overfitting, or multiple-testing errors.</p></div>
    {!query.data?.items.length ? <EmptyState title="No hypotheses" detail="Generate the deterministic semiconductor, airline, and agriculture cases." /> : <div className="source-grid">{query.data.items.map(item => <article className="panel" key={item.id}><p className="eyebrow">{item.company_name}</p><h2>{item.title}</h2><p>{item.economic_rationale}</p><p><span className={`version-chip ${item.status === "REJECTED" ? "danger" : ""}`}>{item.status}</span> · {item.originating_method}</p><Link to={`/research/hypotheses/${item.id}`}>Inspect falsifiable research</Link></article>)}</div>}
  </section>;
}

export function HypothesisDetail() {
  const { id = "" } = useParams();
  const query = useQuery({ queryKey: ["hypothesis", id], queryFn: () => api.hypothesis(id), enabled: Boolean(id) });
  const experiments = useQuery({ queryKey: ["factor-experiments"], queryFn: api.factorExperiments });
  if (query.isLoading) return <LoadingState label="Loading hypothesis rationale and evidence" />;
  if (query.error) return <ErrorState error={query.error} />;
  const item = query.data;
  const experiment = experiments.data?.items.find(value => value.hypothesis_id === id);
  return <section><Link className="back-link" to="/research/hypotheses">← Hypothesis Lab</Link><div className="page-heading"><div><p className="eyebrow">{item?.company_name} · {item?.status}</p><h1>{item?.title}</h1><p>{item?.economic_rationale}</p></div></div>
    <div className="metric-grid"><article className="panel"><h2>{item?.expected_direction}</h2><p>Expected direction</p></article><article className="panel"><h2>{item?.expected_horizon}</h2><p>Expected horizon</p></article><article className="panel"><h2>{item?.mechanism_confidence}</h2><p>Mechanism confidence—not causal proof</p></article></div>
    <article className="panel"><h2>Proposed economic mechanism</h2><pre className="json-block">{JSON.stringify(item?.mechanisms, null, 2)}</pre></article>
    <div className="two-column"><article className="panel"><h2>Supporting and contradicting evidence</h2><pre className="json-block">{JSON.stringify(item?.evidence, null, 2)}</pre></article><article className="panel"><h2>Required datasets</h2><p>{item?.required_datasets.join(" · ")}</p><h3>Candidate feature</h3><pre className="json-block">{JSON.stringify(item?.feature_specs, null, 2)}</pre></article></div>
    <article className="panel"><h2>Falsification conditions</h2><ul>{item?.falsification_criteria.map(value => <li key={value}>{value}</li>)}</ul></article>
    {experiment ? <Link className="primary-link" to={`/research/experiments/${experiment.id}`}>Inspect factor experiment</Link> : null}
  </section>;
}

export function FactorExperimentDetail() {
  const { id = "" } = useParams();
  const query = useQuery({ queryKey: ["factor-experiment", id], queryFn: () => api.factorExperiment(id), enabled: Boolean(id) });
  if (query.isLoading) return <LoadingState label="Loading immutable factor experiment" />;
  if (query.error) return <ErrorState error={query.error} />;
  const item = query.data;
  return <section><Link className="back-link" to={`/research/hypotheses/${item?.hypothesis_id}`}>← Hypothesis</Link><div className="page-heading"><div><p className="eyebrow">IMMUTABLE EXPERIMENT</p><h1>Factor Experiment</h1><p>{item?.status} · {item?.conclusion ?? "pending"} · seed {item?.seed}</p></div></div>
    <div className="partition-strip"><article><b>TRAIN</b><span>Feature and baseline fitting only</span></article><article><b>VALIDATION</b><span>Method selection and robustness</span></article><article><b>FINAL OUT-OF-SAMPLE</b><span>Sealed from hypothesis generation</span></article></div>
    <div className="source-grid"><Link className="panel" to={`/research/experiments/${id}/walk-forward`}><h2>Walk-Forward Results</h2><p>Folds, purging, embargo, warnings, and failures.</p></Link><Link className="panel" to={`/research/experiments/${id}/robustness`}><h2>Robustness Matrix</h2><p>Variants, ablations, and negative controls.</p></Link><Link className="panel" to={`/research/experiments/${id}/statistics`}><h2>Factor Statistics</h2><p>IC, quantiles, coverage, and corrected significance.</p></Link><Link className="panel" to={`/research/experiments/${id}/gates`}><h2>Validation Gates</h2><p>No direct path to paper eligibility.</p></Link></div>
    <article className="panel"><h2>Protocol and reproducibility</h2><pre className="json-block">{JSON.stringify({ validation_protocol: item?.validation_protocol, cost_assumptions: item?.cost_assumptions, dependency_versions: item?.dependency_versions, warnings: item?.warnings }, null, 2)}</pre></article>
  </section>;
}

export function WalkForwardResults() {
  const { id = "" } = useParams();
  const query = useQuery({ queryKey: ["experiment-folds", id], queryFn: () => api.experimentFolds(id), enabled: Boolean(id) });
  if (query.isLoading) return <LoadingState label="Loading walk-forward folds" />;
  if (query.error) return <ErrorState error={query.error} />;
  return <section><Link className="back-link" to={`/research/experiments/${id}`}>← Experiment</Link><div className="page-heading"><div><p className="eyebrow">FAILED FOLDS REMAIN VISIBLE</p><h1>Walk-Forward Results</h1><p>Expanding windows with explicit purge and embargo observations.</p></div></div><div className="table-wrap"><table><thead><tr><th>Fold</th><th>TRAIN</th><th>VALIDATION</th><th>FINAL OOS</th><th>Purge / Embargo</th><th>Rank IC</th><th>Coverage</th></tr></thead><tbody>{query.data?.items.map(fold => <tr key={fold.id}><td>{fold.fold_number + 1}</td><td>{partitionLabel(fold.train[0])} → {partitionLabel(fold.train[1])}</td><td>{partitionLabel(fold.validation[0])} → {partitionLabel(fold.validation[1])}</td><td>{partitionLabel(fold.final_out_of_sample_test[0])} → {partitionLabel(fold.final_out_of_sample_test[1])}</td><td>{fold.purge_observations} / {fold.embargo_observations}</td><td>{Number(fold.factor_statistics.spearman_ic).toFixed(4)}</td><td>{fold.coverage}</td></tr>)}</tbody></table></div></section>;
}

export function RobustnessMatrix() {
  const { id = "" } = useParams();
  const query = useQuery({ queryKey: ["experiment-robustness", id], queryFn: () => api.experimentRobustness(id), enabled: Boolean(id) });
  if (query.isLoading) return <LoadingState label="Attacking the candidate factor" />;
  if (query.error) return <ErrorState error={query.error} />;
  return <section><Link className="back-link" to={`/research/experiments/${id}`}>← Experiment</Link><div className="page-heading"><div><p className="eyebrow">SAVE ALL VARIANTS</p><h1>Robustness Matrix</h1><p>Alternate assumptions, component ablations, and controls are retained whether they pass or fail.</p></div></div><div className="source-grid">{query.data?.variants.map(item => <article className="panel" key={item.type}><h2>{item.type.replaceAll("_", " ")}</h2><p><span className="version-chip">{item.passed ? "PASSED" : "FAILED"}</span></p><pre className="json-block">{JSON.stringify(item.statistics, null, 2)}</pre></article>)}</div><article className="panel"><h2>Ablation results</h2><pre className="json-block">{JSON.stringify(query.data?.ablations, null, 2)}</pre></article><article className="panel"><h2>Negative controls</h2>{query.data?.negative_controls.map(control => <p key={control.control_type}><b>{control.control_type}</b> · methodology {control.methodology_valid ? "valid" : "invalid"} · persistent power {String(control.persistent_power_detected)}</p>)}</article></section>;
}

export function FactorStatisticsPage() {
  const { id = "" } = useParams();
  const query = useQuery({ queryKey: ["experiment-statistics", id], queryFn: () => api.experimentStatistics(id), enabled: Boolean(id) });
  if (query.isLoading) return <LoadingState label="Loading corrected factor statistics" />;
  if (query.error) return <ErrorState error={query.error} />;
  return <section><Link className="back-link" to={`/research/experiments/${id}`}>← Experiment</Link><div className="page-heading"><div><p className="eyebrow">RAW P-VALUES NEVER STAND ALONE</p><h1>Factor Statistics</h1><p>Pearson and rank IC, quantile behavior, coverage, stability, and family-wise corrections.</p></div></div><div className="table-wrap"><table><thead><tr><th>Family</th><th>Raw p-value</th><th>Adjusted p-value</th><th>Method</th><th>Result</th></tr></thead><tbody>{query.data?.multiple_testing.map((item, index) => <tr key={`${item.hypothesis_family}-${index}`}><td>{item.hypothesis_family}</td><td>{item.raw_p_value}</td><td>{item.adjusted_p_value}</td><td>{item.correction_method}</td><td>{item.rejected_null ? "significant after correction" : "not significant"}</td></tr>)}</tbody></table></div></section>;
}

export function ValidationGates() {
  const { id = "" } = useParams();
  const experiment = useQuery({ queryKey: ["factor-experiment", id], queryFn: () => api.factorExperiment(id), enabled: Boolean(id) });
  const hypothesisId = experiment.data?.hypothesis_id ?? "";
  const gates = useQuery({ queryKey: ["promotion-events", hypothesisId], queryFn: () => api.promotionEvents(hypothesisId), enabled: Boolean(hypothesisId) });
  if (experiment.isLoading || gates.isLoading) return <LoadingState label="Loading research promotion gates" />;
  const error = experiment.error ?? gates.error;
  if (error) return <ErrorState error={error} />;
  return <section><Link className="back-link" to={`/research/experiments/${id}`}>← Experiment</Link><div className="page-heading"><div><p className="eyebrow">NO LIVE-TRADING STATUS</p><h1>Validation Gates</h1><p>Evidence → implementation → leakage → backtest → walk-forward → robustness → OOS → paper eligibility.</p></div></div><div className="promotion-flow">{gates.data?.items.map(item => <article className="panel" key={`${item.to_stage}-${item.decision}`}><p className="eyebrow">{item.decision}</p><h2>{item.to_stage}</h2><p>{item.reasons.join(" · ")}</p></article>)}</div></section>;
}

export function ResearchEngineStatusPage() {
  const qlib = useQuery({ queryKey: ["qlib-research-status"], queryFn: api.qlibResearchStatus });
  const rdAgent = useQuery({ queryKey: ["rd-agent-research-status"], queryFn: api.rdAgentResearchStatus });
  if (qlib.isLoading || rdAgent.isLoading) return <LoadingState label="Checking optional research engines" />;
  const error = qlib.error ?? rdAgent.error;
  if (error) return <ErrorState error={error} />;
  return <section><div className="page-heading"><div><p className="eyebrow">OPTIONAL · ISOLATED · DISABLED BY DEFAULT</p><h1>Research Engine Status</h1><p>MIL remains authoritative for Temporal Truth, snapshots, lineage, budgets, and audit history.</p></div></div><div className="source-grid">{[qlib.data, rdAgent.data].map(item => item ? <article className="panel" key={item.engine}><h2>{item.engine}</h2><p><span className="version-chip">{item.available ? "AVAILABLE" : "UNAVAILABLE"}</span> · enabled {String(item.enabled)}</p><p>{item.message}</p><h3>Security boundaries</h3><ul>{item.security_boundaries.map(value => <li key={value}>{value}</li>)}</ul></article> : null)}</div></section>;
}
