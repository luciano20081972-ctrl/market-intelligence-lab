import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api";
import {
  FactorExperimentDetail,
  FactorStatisticsPage,
  HypothesisDetail,
  HypothesisLab,
  ResearchEngineStatusPage,
  RobustnessMatrix,
  ValidationGates,
  WalkForwardResults,
} from "../pages/HypothesisPlatform";
import { renderPage } from "./render";

vi.mock("../api", () => ({ api: {
  hypotheses: vi.fn(), hypothesis: vi.fn(), runHypothesisFixture: vi.fn(),
  factorExperiments: vi.fn(), factorExperiment: vi.fn(), experimentFolds: vi.fn(),
  experimentStatistics: vi.fn(), experimentRobustness: vi.fn(), promotionEvents: vi.fn(),
  qlibResearchStatus: vi.fn(), rdAgentResearchStatus: vi.fn(),
} }));
const mocked = vi.mocked(api);
const hypothesis = {
  id: "hypothesis-1", subject_entity_id: "entity-1", company_name: "Silica Systems",
  title: "Electricity pressure may precede margin changes", type: "economic_mechanism",
  economic_rationale: "Energy-intensive fabrication links regional power costs to margins.",
  mechanism: { terminology: "hypothesized transmission path" }, expected_direction: "negative",
  expected_horizon: "90 observations", required_evidence: [], required_graph_drivers: ["EIA"],
  required_datasets: ["eia.electricity", "sec.companyfacts"], proposed_outcome: { key: "margin" },
  candidate_feature_specification: { feature_key: "weighted_electricity_change" },
  originating_method: "deterministic_graph_derived",
  falsification_criteria: ["No OOS persistence", "FDR failure"], mechanism_confidence: "0.78",
  novelty_estimate: "0.71", assumptions: ["Not causal proof"],
  simulation_eligible_time: "2026-02-01T12:00:00Z", status: "VALIDATED", version: 1,
  semantics: "research_hypothesis_not_investment_prediction",
  mechanisms: [{ source_driver: "EIA electricity prices", relationship_path: ["Region", "Facility", "Company"] }],
  evidence: [{ stance: "supporting", summary: "Point-in-time evidence" }],
  feature_specs: [{ feature_key: "weighted_electricity_change", lookback: 90, lag: 1 }],
};
const experiment = {
  id: "experiment-1", hypothesis_id: "hypothesis-1", candidate_feature_spec_id: "spec-1",
  universe_version_id: "universe-1", feature_snapshot_id: "snapshot-1",
  outcome_definition_id: "outcome-1", status: "COMPLETED", conclusion: "PROMISING",
  period_start: "2023-01-01T00:00:00Z", period_end: "2026-01-01T00:00:00Z",
  validation_protocol: { generator_final_test_access: false }, cost_assumptions: { bps: 5 },
  dependency_versions: { scipy: "1.18.0" }, seed: 10000,
  warnings: ["RESEARCH_RESULT_NOT_INVESTMENT_RECOMMENDATION"], immutable: true,
};

beforeEach(() => {
  vi.clearAllMocks();
  mocked.hypotheses.mockResolvedValue({ items: [hypothesis, { ...hypothesis, id: "hypothesis-2", title: "Plausible but rejected factor", status: "REJECTED" }], total: 2, high_rejection_rate_expected: true });
  mocked.hypothesis.mockResolvedValue(hypothesis);
  mocked.runHypothesisFixture.mockResolvedValue({ hypothesis_count: 3 });
  mocked.factorExperiments.mockResolvedValue({ items: [experiment], total: 1 });
  mocked.factorExperiment.mockResolvedValue(experiment);
  mocked.experimentFolds.mockResolvedValue({ items: [{ id: "fold-1", fold_number: 0,
    train: ["2023-01-01T00:00:00Z", "2024-01-01T00:00:00Z"],
    validation: ["2024-01-07T00:00:00Z", "2024-04-01T00:00:00Z"],
    final_out_of_sample_test: ["2024-04-07T00:00:00Z", "2024-07-01T00:00:00Z"],
    purge_observations: 5, embargo_observations: 5, observations: 60, coverage: "1.0",
    factor_statistics: { spearman_ic: 0.06 }, model_statistics: { mse_improvement: 0.02 },
    warnings: [], failures: [] }], total: 1, failed_folds_are_retained: true });
  mocked.experimentStatistics.mockResolvedValue({ items: [], multiple_testing: [{
    hypothesis_family: "semiconductor-family", number_of_hypotheses: 3,
    raw_p_value: "0.004", adjusted_p_value: "0.012", correction_method: "benjamini-hochberg",
    rejected_null: true }], raw_p_values_never_reported_alone: true });
  mocked.experimentRobustness.mockResolvedValue({ variants: [{ type: "alternate_lookback",
    parameters: { lookback: 120 }, statistics: { rank_ic: 0.05 }, passed: true }],
    ablations: [{ component: "energy", included_components: ["energy"],
      statistics: { rank_ic: 0.03 }, contribution: "0.03" }], negative_controls: [{
      control_type: "shuffled", statistics: { rank_ic: 0 }, persistent_power_detected: false,
      methodology_valid: true }] });
  mocked.promotionEvents.mockResolvedValue({ items: [
    { from_stage: null, to_stage: "DRAFT", decision: "passed", reasons: ["created"], gate_version: "v1" },
    { from_stage: "DRAFT", to_stage: "EVIDENCE_CHECKED", decision: "passed", reasons: ["evidence"], gate_version: "v1" },
  ], total: 2, live_trading_status_exists: false });
  mocked.qlibResearchStatus.mockResolvedValue({ engine: "qlib", version: null, available: false,
    enabled: false, message: "optional and unavailable", capabilities: ["snapshot_input"],
    security_boundaries: ["MIL remains canonical storage"] });
  mocked.rdAgentResearchStatus.mockResolvedValue({ engine: "rd-agent", version: null,
    available: false, enabled: false, message: "Linux/Docker-oriented and unavailable",
    capabilities: ["candidate_artifact"], security_boundaries: ["no production secrets"] });
});

describe("Sprint 10 hypothesis research pages", () => {
  it("shows validated and rejected hypotheses without recommendations", async () => {
    renderPage(<HypothesisLab />);
    expect(await screen.findByText("Electricity pressure may precede margin changes")).toBeInTheDocument();
    expect(screen.getByText("Plausible but rejected factor")).toBeInTheDocument();
    expect(screen.getByText("SCIENTIFIC RESEARCH · NOT PREDICTION")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Generate fixture hypotheses" }));
    expect(mocked.runHypothesisFixture).toHaveBeenCalledOnce();
  });

  it("renders rationale mechanism evidence feature and falsification", async () => {
    renderPage(<HypothesisDetail />, "/research/hypotheses/hypothesis-1", "/research/hypotheses/:id");
    expect(await screen.findByText(/Energy-intensive fabrication/)).toBeInTheDocument();
    expect(screen.getByText(/EIA electricity prices/)).toBeInTheDocument();
    expect(screen.getByText("FDR failure")).toBeInTheDocument();
  });

  it("separates train validation and final out-of-sample", async () => {
    renderPage(<FactorExperimentDetail />, "/research/experiments/experiment-1", "/research/experiments/:id");
    expect(await screen.findByText("TRAIN")).toBeInTheDocument();
    expect(screen.getByText("VALIDATION")).toBeInTheDocument();
    expect(screen.getByText("FINAL OUT-OF-SAMPLE")).toBeInTheDocument();
  });

  it("shows walk-forward purge and embargo boundaries", async () => {
    renderPage(<WalkForwardResults />, "/research/experiments/experiment-1/walk-forward", "/research/experiments/:id/walk-forward");
    expect(await screen.findByText("Walk-Forward Results")).toBeInTheDocument();
    expect(screen.getByText("5 / 5")).toBeInTheDocument();
  });

  it("shows robustness ablation and negative controls", async () => {
    renderPage(<RobustnessMatrix />, "/research/experiments/experiment-1/robustness", "/research/experiments/:id/robustness");
    expect(await screen.findByText("alternate lookback")).toBeInTheDocument();
    expect(screen.getByText(/shuffled/)).toBeInTheDocument();
    expect(screen.getByText(/methodology valid/)).toBeInTheDocument();
  });

  it("always pairs raw and adjusted significance", async () => {
    renderPage(<FactorStatisticsPage />, "/research/experiments/experiment-1/statistics", "/research/experiments/:id/statistics");
    expect(await screen.findByText("0.004")).toBeInTheDocument();
    expect(screen.getByText("0.012")).toBeInTheDocument();
    expect(screen.getByText("benjamini-hochberg")).toBeInTheDocument();
  });

  it("renders sequential research promotion gates", async () => {
    renderPage(<ValidationGates />, "/research/experiments/experiment-1/gates", "/research/experiments/:id/gates");
    expect(await screen.findByText("EVIDENCE_CHECKED")).toBeInTheDocument();
    expect(screen.getByText("NO LIVE-TRADING STATUS")).toBeInTheDocument();
  });

  it("shows Qlib and RD-Agent as optional disabled engines", async () => {
    renderPage(<ResearchEngineStatusPage />);
    expect(await screen.findByText("qlib")).toBeInTheDocument();
    expect(screen.getByText("rd-agent")).toBeInTheDocument();
    expect(screen.getAllByText(/enabled false/)).toHaveLength(2);
  });
});
