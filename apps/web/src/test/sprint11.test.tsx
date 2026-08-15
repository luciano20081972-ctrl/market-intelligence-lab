import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api";
import {
  DivergenceDetailPage,
  DivergenceMonitorPage,
  FactorClustersPage,
  FactorRedundancyPage,
  InformationValuePage,
  ResearchContradictionsPage,
  ResearchMemoryDetail,
  ResearchMemoryPage,
  ResearchMethodReliabilityPage,
  ResearchRegimeContextPage,
  SignalIndependencePage,
} from "../pages/ResearchIntelligence";
import { renderPage } from "./render";

vi.mock("../api", () => ({ api: {
  researchMemory: vi.fn(), researchMemoryDetail: vi.fn(), runResearchIntelligenceFixture: vi.fn(),
  researchContradictions: vi.fn(), researchRegimes: vi.fn(), signalIndependence: vi.fn(),
  factorRedundancy: vi.fn(), factorClusters: vi.fn(), divergenceEvents: vi.fn(),
  divergenceEvent: vi.fn(), informationValue: vi.fn(), researchMethodReliability: vi.fn(),
} }));
const mocked = vi.mocked(api);
const memory = {
  id: "memory-1", hypothesis_id: "hypothesis-1", experiment_id: "experiment-1",
  subject_entity_id: "entity-1", company_name: "Harvest Fields Cooperative",
  feature_key: "water_energy_pressure", outcome_key: "revenue_growth", conclusion: "NEGATIVE" as const,
  status: "ACTIVE" as const, datasets: ["weather", "energy"], feature_domains: ["agriculture"],
  applicability: { business_model: "agricultural cooperative", sector: "agriculture" },
  regime_context: ["high inflation"], period_context: { final_oos: "2025" },
  result_summary: { oos: [{ rank_ic: 0 }] }, failure_reasons: ["no OOS persistence"],
  success_conditions: [], failure_conditions: ["multiple-testing failure"], confidence: "0.900000",
  first_learned_at: "2026-02-15T12:00:00Z", last_confirmed_at: "2026-02-15T12:00:00Z",
  simulation_eligible_time: "2026-02-15T12:00:00Z", graph_path: [], provenance: { immutable: true },
  memory_decisions: [{ classification: "KNOWN_FAILURE", decision: "SUPPRESSED",
    reason: "Equivalent robust rejection exists", override_authorized: false,
    policy_version: "memory-policy-v1" }],
};
const independence = [{ id: "analysis-a", experiment_id: "experiment-a",
  factor_key: "conventional-overlap-factor", baseline_version: "conventional-baseline-v1",
  methodology_version: "signal-independence-v1", predictive_strength: "0.98",
  independent_contribution: "0.08", redundancy_score: "0.97",
  independent_information_score: "0.18", components: {}, formula: { version: "v1" },
  segments: {}, as_of_time: "2026-02-15T12:00:00Z",
  semantics: "predictive_is_not_independent" }, { id: "analysis-b", experiment_id: "experiment-b",
  factor_key: "external-driver-independent-factor", baseline_version: "conventional-baseline-v1",
  methodology_version: "signal-independence-v1", predictive_strength: "0.62",
  independent_contribution: "0.55", redundancy_score: "0.12",
  independent_information_score: "0.71", components: {}, formula: { version: "v1" },
  segments: {}, as_of_time: "2026-02-15T12:00:00Z",
  semantics: "predictive_is_not_independent" }];
const divergence = { id: "divergence-1", definition_id: "definition-1", subject_entity_id: "airline-1",
  company_name: "Meridian Air", as_of_time: "2026-02-15T12:00:00Z",
  domain_values: { fundamentals: { raw: 0.7, normalized: 0.7 }, market: { raw: 0.6, normalized: 0.6 },
    external_driver: { raw: -0.9, normalized: -0.9 } },
  magnitude_components: { max_minus_min: 1.6, sign_disagreement: true },
  disagreement_magnitude: "1.60000000", persistence_periods: 3, data_completeness: "1.000000",
  evidence: { temporal_truth: true }, historical_analogues: [{ sample_size: 1, warning: "tiny sample" }],
  confidence: "0.88", research_priority: "0.90", status: "DETECTED", research_candidate_id: null,
  paper_eligible: false as const, semantics: "divergent_not_mispriced" };

beforeEach(() => {
  vi.clearAllMocks();
  mocked.researchMemory.mockResolvedValue({ items: [memory] });
  mocked.researchMemoryDetail.mockResolvedValue(memory);
  mocked.runResearchIntelligenceFixture.mockResolvedValue({ memory_count: 3 });
  mocked.researchContradictions.mockResolvedValue({ items: [{ id: "c1",
    conflicting_dimension: "business_model_applicability", confidence: "0.8",
    possible_explanations: ["different business models"] }] });
  mocked.researchRegimes.mockResolvedValue({ definitions: [{ id: "r1", label: "High inflation",
    method: { no_future_data: true } }], assignments: [{ id: "a1" }] });
  mocked.signalIndependence.mockResolvedValue({ items: independence });
  mocked.factorRedundancy.mockResolvedValue({ items: [{ id: "f1", factor_a: "factor A",
    factor_b: "baseline", methodology: "correlation+residualization", result: { pearson: 0.98 } }] });
  mocked.factorClusters.mockResolvedValue({ items: [{ id: "cluster-1", information_family: "energy",
    members: ["factor B"], methodology: { causal_claim: false } }], causal_structure_claimed: false });
  mocked.divergenceEvents.mockResolvedValue({ items: [divergence] });
  mocked.divergenceEvent.mockResolvedValue(divergence);
  mocked.informationValue.mockResolvedValue({ items: [{ id: "iv1", resource_key: "energy data",
    metrics: { independent_contributions: 3 }, recommendation: "Prioritize bounded research", sample_size: 4 }],
    semantics: "research_resource_efficiency_not_investment_roi" });
  mocked.researchMethodReliability.mockResolvedValue({ items: [{ id: "m1", method: "graph-derived",
    metrics: { oos_survival: 0.35 }, interpretation: "Sample too small to rank as best" }] });
});

describe("Sprint 11 research intelligence pages", () => {
  it("keeps negative memory visible and loads deterministic memory", async () => {
    renderPage(<ResearchMemoryPage />);
    expect(await screen.findByText("WHAT FAILED?")).toBeInTheDocument();
    expect(screen.getByText("no OOS persistence")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Load reference research memory" }));
    expect(mocked.runResearchIntelligenceFixture).toHaveBeenCalledOnce();
  });

  it("explains applicability and known-failure suppression", async () => {
    renderPage(<ResearchMemoryDetail />, "/research/memory/memory-1", "/research/memory/:id");
    expect((await screen.findAllByText(/agricultural cooperative/)).length).toBeGreaterThan(0);
    expect(screen.getByText(/KNOWN_FAILURE/)).toBeInTheDocument();
    expect(screen.getByText(/Equivalent robust rejection/)).toBeInTheDocument();
  });

  it("shows contradictions and point-in-time regimes without causal claims", async () => {
    renderPage(<ResearchContradictionsPage />);
    expect(await screen.findByText("business_model_applicability")).toBeInTheDocument();
    renderPage(<ResearchRegimeContextPage />);
    expect(await screen.findByText("High inflation")).toBeInTheDocument();
    expect(screen.getByText(/no_future_data/)).toBeInTheDocument();
  });

  it("separates predictive strength from independent contribution", async () => {
    renderPage(<SignalIndependencePage />);
    expect(await screen.findByText("0.98")).toBeInTheDocument();
    expect(screen.getByText("0.55")).toBeInTheDocument();
    expect(screen.getAllByText(/Independent does not mean causal/)).toHaveLength(2);
  });

  it("renders redundancy and non-causal information families", async () => {
    renderPage(<FactorRedundancyPage />);
    expect(await screen.findByText("correlation+residualization")).toBeInTheDocument();
    renderPage(<FactorClustersPage />);
    expect(await screen.findByText("energy")).toBeInTheDocument();
    expect(screen.getByText(/do not prove causal structure/)).toBeInTheDocument();
  });

  it("detects divergence but never presents a trade status", async () => {
    renderPage(<DivergenceMonitorPage />);
    expect(await screen.findByText("Meridian Air")).toBeInTheDocument();
    expect(screen.getByText(/DIVERGENT ≠ MISPRICED/)).toBeInTheDocument();
    renderPage(<DivergenceDetailPage />, "/research/divergence/divergence-1", "/research/divergence/:id");
    expect(await screen.findByText(/no paper eligibility/)).toBeInTheDocument();
    expect(screen.getByText(/tiny samples imply no strength/)).toBeInTheDocument();
  });

  it("reports information value and method reliability with sample safeguards", async () => {
    renderPage(<InformationValuePage />);
    expect(await screen.findByText("energy data")).toBeInTheDocument();
    expect(screen.getByText(/no dataset is automatically disabled/i)).toBeInTheDocument();
    renderPage(<ResearchMethodReliabilityPage />);
    expect(await screen.findByText("graph-derived")).toBeInTheDocument();
    expect(screen.getByText(/too small to rank as best/i)).toBeInTheDocument();
  });
});
