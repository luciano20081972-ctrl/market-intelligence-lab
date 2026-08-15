import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api";
import {
  AdversarialReviewPage,
  CounterfactualLabPage,
  ResearchConfidencePage,
  ResearchDossierPage,
  ScenarioLabPage,
  SkepticChallengesPage,
} from "../pages/AdversarialIntelligence";
import { renderPage } from "./render";

vi.mock("../api", () => ({ api: {
  skepticReviews: vi.fn(), skepticChallenges: vi.fn(), researchConfidence: vi.fn(),
  scenarios: vi.fn(), counterfactuals: vi.fn(), researchDossiers: vi.fn(), runAdversarialFixture: vi.fn(),
} }));

const mocked = vi.mocked(api);

beforeEach(() => {
  mocked.skepticReviews.mockResolvedValue({ items: [{ id: "r1", status: "BLOCKED", policy_version: "v1" }] });
  mocked.skepticChallenges.mockResolvedValue({ items: [{ id: "c1", title: "Entity ambiguity", severity: "CRITICAL", status: "OPEN", evidence: {}, proposed_test: "Resolve entity", resolution: {} }] });
  mocked.researchConfidence.mockResolvedValue({ items: [{ id: "p1", classification: "FRAGILE", formula_version: "v1", components: { temporal_safety: 1 } }] });
  mocked.scenarios.mockResolvedValue({ items: [{ id: "s1", title: "Energy stress", description: "Electricity +20%", scenario_type: "STRESS", plausibility: "MEDIUM" }] });
  mocked.counterfactuals.mockResolvedValue({ items: [{ id: "f1", title: "Remove energy", identification_status: "SIMULATED_MECHANISM" }] });
  mocked.researchDossiers.mockResolvedValue({ items: [{ id: "d1", title: "Semiconductor dossier" }] });
});

describe("v0.12 scientific views", () => {
  it("shows blocking adversarial review and structured challenge fields", async () => {
    renderPage(<AdversarialReviewPage />);
    expect(await screen.findByText("BLOCKED")).toBeInTheDocument();
    renderPage(<SkepticChallengesPage />);
    expect(await screen.findByText("CRITICAL")).toBeInTheDocument();
    expect(screen.getByText("TEST")).toBeInTheDocument();
  });

  it("labels scenarios as scenarios rather than forecasts", async () => {
    renderPage(<ScenarioLabPage />);
    expect(screen.getByText("THIS IS A SCENARIO, NOT A FORECAST")).toBeInTheDocument();
    expect(await screen.findByText("Energy stress")).toBeInTheDocument();
  });

  it("labels counterfactuals as simulated and not causal", async () => {
    renderPage(<CounterfactualLabPage />);
    expect(screen.getByText("THIS IS A SIMULATED ALTERNATIVE STATE, NOT PROVEN CAUSAL EFFECT")).toBeInTheDocument();
    expect(await screen.findByText("SIMULATED_MECHANISM")).toBeInTheDocument();
  });

  it("shows transparent confidence and recommendation-free dossiers", async () => {
    renderPage(<ResearchConfidencePage />);
    expect(await screen.findByText(/not a probability/i)).toBeInTheDocument();
    renderPage(<ResearchDossierPage />);
    expect(await screen.findByText(/never a BUY\/SELL recommendation/i)).toBeInTheDocument();
  });
});
