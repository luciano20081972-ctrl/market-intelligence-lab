import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api";
import { CompanyDriverProfile } from "../pages/CompanyDriverProfile";
import { DataRelevance } from "../pages/DataRelevance";
import { EconomicGraphExplorer } from "../pages/EconomicGraphExplorer";
import { EntityResolutionReview } from "../pages/EntityResolutionReview";
import { RelationshipEvidence } from "../pages/RelationshipEvidence";
import type { EconomicEntity } from "../types";
import { renderPage } from "./render";

vi.mock("../api", () => ({ api: {
  economicEntities: vi.fn(), economicGraph: vi.fn(), companyDriverProfile: vi.fn(),
  relationshipEvidence: vi.fn(), dataRelevance: vi.fn(), resolutionCandidates: vi.fn(),
  decideResolution: vi.fn(),
} }));
const mocked = vi.mocked(api);
const company: EconomicEntity = {
  id: "company-1", entity_type: "Company", canonical_name: "Silica Systems", status: "verified",
  valid_from: "2026-01-01T00:00:00Z", valid_to: null, first_seen: "2026-01-01T00:00:00Z",
  last_verified: "2026-01-01T00:00:00Z", simulation_eligible_time: "2026-01-01T00:00:00Z",
  confidence: "0.95", provenance: { source: "fixture" },
};

beforeEach(() => {
  vi.clearAllMocks();
  mocked.economicEntities.mockResolvedValue({ items: [company], page: 1, page_size: 50, total: 1 });
  mocked.economicGraph.mockResolvedValue({
    as_of: "2026-01-02T00:00:00Z", max_depth: 3, max_nodes: 100, nodes: [company],
    relationships: [], paths: [], path_explanations: [], truncated: false,
  });
  mocked.companyDriverProfile.mockResolvedValue({
    id: "profile-1", company_entity_id: company.id, prior_version: "driver-priors-v1", version: 1,
    generated_at: "2026-01-02T00:00:00Z", simulation_eligible_time: "2026-01-02T00:00:00Z",
    trigger_reason: "fixture", scientific_label: "potential driver; not a historically validated factor",
    entries: [{ id: "entry-1", driver_category: "technology", linked_entity_ids: ["tech-1"],
      supporting_relationship_ids: ["relationship-1"], prior_relevance: "0.90",
      evidence_relevance: "0.80", historical_evidence_relevance: null, user_override: null,
      effective_relevance: "0.85", confidence: "0.88", explanation: "Evidence-backed technology exposure." }],
  });
  mocked.relationshipEvidence.mockResolvedValue({ items: [{
    id: "evidence-1", relationship_id: "relationship-1", direction: "supporting",
    source_record_identifier: "SEC-FIXTURE-1", evidence_type: "SEC filing",
    publication_time: "2026-01-01T00:00:00Z", simulation_eligible_time: "2026-01-01T00:00:00Z",
    confidence: "0.90", content_reference: "fixture://sec/1", supporting_text: "Structured filing fact",
  }], total: 1 });
  mocked.dataRelevance.mockResolvedValue({ company_entity_id: company.id, profile_id: "profile-1",
    router_version: "relevance-router-v1", items: [{ id: "route-1", dataset_id: "EIA_ELECTRICITY",
      decision: "PROCESS", relevance_score: "0.86", reason_codes: ["DRIVER_ENERGY"],
      supporting_graph_paths: [{ relationship_ids: ["relationship-1"] }], confidence: "0.84",
      created_at: "2026-01-02T00:00:00Z" }], total: 1 });
  mocked.resolutionCandidates.mockResolvedValue({ items: [{ id: "candidate-1", namespace: "ticker",
    value: "SILI", normalized_value: "SILI", candidate_entity_id: company.id, method: "normalized",
    confidence: "0.72", source: "fixture", evidence: {}, resolver_version: "resolver-v1",
    status: "candidate", resolved_at: "2026-01-02T00:00:00Z" }], total: 1 });
  mocked.decideResolution.mockResolvedValue({ id: "decision-1", candidate_id: "candidate-1", decision: "confirmed" });
});

describe("Sprint 8 company intelligence pages", () => {
  it("renders a bounded economic graph", async () => {
    renderPage(<EconomicGraphExplorer />);
    expect(await screen.findByRole("heading", { name: "Economic Graph Explorer" })).toBeInTheDocument();
    expect(await screen.findByText("Silica Systems")).toBeInTheDocument();
    expect(await screen.findByText("Maximum 3 hops")).toBeInTheDocument();
  });

  it("renders only evidence-backed company driver entries prominently", async () => {
    renderPage(<CompanyDriverProfile />);
    expect(await screen.findByText("85% relevance")).toBeInTheDocument();
    expect(screen.getByText(/not a historically validated factor/)).toBeInTheDocument();
    expect(screen.getByText("technology")).toBeInTheDocument();
  });

  it("renders relationship provenance", async () => {
    renderPage(<RelationshipEvidence />);
    expect(await screen.findByText("SEC-FIXTURE-1")).toBeInTheDocument();
    expect(screen.getByText("fixture://sec/1")).toBeInTheDocument();
  });

  it("renders deterministic dataset routing", async () => {
    renderPage(<DataRelevance />);
    expect(await screen.findByText("EIA_ELECTRICITY")).toBeInTheDocument();
    expect(screen.getByText("PROCESS")).toBeInTheDocument();
    expect(screen.getByText("DRIVER_ENERGY")).toBeInTheDocument();
  });

  it("allows an admin to confirm an ambiguous mapping", async () => {
    renderPage(<EntityResolutionReview />);
    expect(await screen.findByText("ticker: SILI")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Confirm" }));
    expect(mocked.decideResolution).toHaveBeenCalledWith(
      "candidate-1", "confirm", "Manual confirm from resolution review",
    );
  });
});
