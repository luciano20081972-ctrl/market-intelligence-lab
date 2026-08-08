import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api";
import {
  FeatureCatalog,
  FeatureExplorer,
  FeatureLineageViewer,
  ResearchBudgetDashboard,
  ResearchCandidateDetail,
  ResearchFunnel,
  ResearchUniversePage,
  ScreeningRunDetail,
} from "../pages/ResearchPlatform";
import { renderPage } from "./render";

vi.mock("../api", () => ({ api: {
  researchUniverses: vi.fn(), researchFeatures: vi.fn(), featureValues: vi.fn(),
  featureLineage: vi.fn(), screeningRuns: vi.fn(), screeningRun: vi.fn(),
  runReferenceScreening: vi.fn(), researchCandidates: vi.fn(), researchCandidate: vi.fn(),
  researchBudgets: vi.fn(),
} }));
const mocked = vi.mocked(api);
const run = {
  id: "run-1", as_of_time: "2026-02-01T12:00:00Z", total_candidates: 100,
  promoted: 50, deferred: 50, demoted: 0, rejected: 0, budget_usage: {},
  reason_distribution: { DATA_COMPLETE: 100 }, checksum: "a".repeat(64),
  funnel: { LEVEL_0: 100, LEVEL_1: 50, LEVEL_2: 20, LEVEL_3: 8, LEVEL_4: 3 },
  decisions: [{ id: "decision-1", entity_id: "entity-123456", score: "0.9",
    score_components: { data_completeness: "1" }, recommendation: "promote",
    reason_codes: ["DATA_COMPLETE"], missing_information: [], level: "LEVEL_4" }],
};

beforeEach(() => {
  vi.clearAllMocks();
  mocked.researchUniverses.mockResolvedValue({ items: [{ id: "universe-1",
    name: "Synthetic 100-Company Research Universe", description: "Point-in-time fixture",
    source: "deterministic-v0.9-fixture", owner_type: "system", selection_rules: { count: 100 } }], total: 1 });
  mocked.researchFeatures.mockResolvedValue({ items: [{ id: "feature-1",
    feature_key: "revenue_growth_yoy", name: "Revenue Growth Yoy", description: "Measurement",
    domain: "fundamental", entity_type: "Company", status: "active" }], total: 1,
    scientific_semantics: "measurement_not_alpha" });
  mocked.featureValues.mockResolvedValue({ items: [{ id: "value-1", feature_key: "revenue_growth_yoy",
    entity_id: "entity-123456", observation_time: "2026-01-20T00:00:00Z",
    simulation_eligible_time: "2026-01-25T00:00:00Z", value: "0.25", unit: "ratio",
    quality_state: "complete", input_checksum: "b".repeat(64), computation_checksum: "c".repeat(64) }],
    total: 1, point_in_time_safe: true });
  mocked.featureLineage.mockResolvedValue({ feature_value_id: "value-1",
    source_observation_refs: [{ source: "SEC" }], graph_relationship_ids: ["edge-1"],
    computation_version: "mil-feature-v1", lineage_checksum: "d".repeat(64) });
  mocked.screeningRuns.mockResolvedValue({ items: [run], total: 1 });
  mocked.screeningRun.mockResolvedValue(run);
  mocked.runReferenceScreening.mockResolvedValue({ screening_run_id: "run-1" });
  mocked.researchCandidates.mockResolvedValue({ items: [{ id: "candidate-1", entity_id: "entity-1",
    company_name: "Silica Systems", archetype: "semiconductor", current_level: "LEVEL_4",
    previous_level: "LEVEL_3", promotion_reason: "DATA_COMPLETE", demotion_reason: null,
    budget_impact: { rank: 1 }, next_review_time: "2026-03-01T00:00:00Z" }], total: 1,
    semantics: "research_priority_not_recommendation" });
  mocked.researchCandidate.mockResolvedValue({ id: "candidate-1", entity_id: "entity-1",
    company_name: "Silica Systems", archetype: "semiconductor", current_level: "LEVEL_4",
    previous_level: "LEVEL_3", promotion_reason: "DATA_COMPLETE", demotion_reason: null,
    budget_impact: { rank: 1 }, next_review_time: "2026-03-01T00:00:00Z",
    selected_pipelines: ["technology", "geopolitical", "energy"], irrelevant_pipelines_skipped: true });
  mocked.researchBudgets.mockResolvedValue({ items: [{ id: "budget-1", level: "LEVEL_3",
    limits: { maximum_companies: 8, cpu_seconds: 32, api_requests_per_company: 1 },
    cost_class: "high", monetary_estimate: null }], total: 1 });
});

describe("Sprint 9 progressive research pages", () => {
  it("renders point-in-time universe provenance", async () => {
    renderPage(<ResearchUniversePage />);
    expect(await screen.findByText("Synthetic 100-Company Research Universe")).toBeInTheDocument();
    expect(screen.getByText("deterministic-v0.9-fixture")).toBeInTheDocument();
  });

  it("labels features as measurements rather than alpha", async () => {
    renderPage(<FeatureCatalog />);
    expect(await screen.findByText("Revenue Growth Yoy")).toBeInTheDocument();
    expect(screen.getByText("MEASUREMENTS, NOT ALPHA")).toBeInTheDocument();
  });

  it("renders an explicitly point-in-time safe feature matrix", async () => {
    renderPage(<FeatureExplorer />);
    expect(await screen.findByText("POINT-IN-TIME SAFE")).toBeInTheDocument();
    expect(screen.getByText("revenue_growth_yoy")).toBeInTheDocument();
  });

  it("renders the configured 100 to 3 research funnel", async () => {
    renderPage(<ResearchFunnel />);
    expect(await screen.findByText("AI Candidates")).toBeInTheDocument();
    expect(screen.getByText("100")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Run reference screen" }));
    expect(mocked.runReferenceScreening).toHaveBeenCalledOnce();
  });

  it("decomposes screening decisions with reason codes", async () => {
    renderPage(<ScreeningRunDetail />, "/research/screening-runs/run-1", "/research/screening-runs/:id");
    expect(await screen.findByText("DATA_COMPLETE")).toBeInTheDocument();
    expect(screen.getByText("LEVEL_4")).toBeInTheDocument();
  });

  it("shows different routed company pipelines and skipped irrelevant work", async () => {
    renderPage(<ResearchCandidateDetail />, "/research/candidates/candidate-1", "/research/candidates/:id");
    expect(await screen.findByText("Silica Systems")).toBeInTheDocument();
    expect(screen.getByText("technology · geopolitical · energy")).toBeInTheDocument();
    expect(screen.getByText("Irrelevant pipelines skipped")).toBeInTheDocument();
  });

  it("shows budget limits before expensive execution", async () => {
    renderPage(<ResearchBudgetDashboard />);
    expect(await screen.findByText("Maximum companies: 8")).toBeInTheDocument();
    expect(screen.getByText("API requests/company: 1")).toBeInTheDocument();
  });

  it("traces feature lineage to inputs, graph, and computation", async () => {
    renderPage(<FeatureLineageViewer />, "/research/lineage/value-1", "/research/lineage/:id");
    expect(await screen.findByText(/mil-feature-v1/)).toBeInTheDocument();
    expect(screen.getByText(/edge-1/)).toBeInTheDocument();
  });
});
