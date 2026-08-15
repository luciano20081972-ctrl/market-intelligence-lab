import { fireEvent, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api";
import { CalibrationPage, OutcomeMonitorPage, PaperPortfolioLabPage, ProspectiveForecastsPage } from "../pages/ProspectiveIntelligence";
import { renderPage } from "./render";

vi.mock("../api", () => ({ api: {
  prospectiveForecasts: vi.fn(), forecastOutcomes: vi.fn(), forecastCalibration: vi.fn(),
  confidenceCalibration: vi.fn(), researchReliabilityV13: vi.fn(), feedbackRecommendations: vi.fn(),
  paperAllocationCandidates: vi.fn(), previewPaperPlan: vi.fn(), paperEvaluationV13: vi.fn(), paperAttributionV13: vi.fn(),
} }));

const mocked = vi.mocked(api);

beforeEach(() => {
  mocked.prospectiveForecasts.mockResolvedValue({ items: [{ id: "f1", forecast_type: "PROBABILITY", evaluation_mode: "PROSPECTIVE", state: "LOCKED", outcome_eligible_time: "2026-10-01", checksum: "a".repeat(64) }] });
  mocked.forecastOutcomes.mockResolvedValue({ items: [] });
  mocked.forecastCalibration.mockResolvedValue({ sample_count: 5, status: "INSUFFICIENT_SAMPLE" });
  mocked.paperAllocationCandidates.mockResolvedValue({ items: [] });
  mocked.previewPaperPlan.mockResolvedValue({ status: "APPROVED_FOR_SIMULATION", label: "SIMULATED / PAPER ONLY", brokerage_connectivity: false, order_preview: [] });
});

describe("v0.13 prospective and paper-only views", () => {
  it("distinguishes evaluation populations and frozen state", async () => {
    renderPage(<ProspectiveForecastsPage />);
    expect(await screen.findByText("PROBABILITY")).toBeInTheDocument();
    expect(screen.getAllByText("PROSPECTIVE").length).toBeGreaterThan(0);
    expect(screen.getByText("HISTORICAL REPLAY")).toBeInTheDocument();
    expect(screen.getByText("FIXTURE")).toBeInTheDocument();
    expect(screen.getByText("LOCKED")).toBeInTheDocument();
  });

  it("labels immature outcome and small calibration state", async () => {
    renderPage(<OutcomeMonitorPage />);
    expect(await screen.findByText(/Early outcomes are rejected/)).toBeInTheDocument();
    renderPage(<CalibrationPage />);
    expect(await screen.findByText("INSUFFICIENT_SAMPLE")).toBeInTheDocument();
    expect(screen.getByText(/confidence is a decomposition/i)).toBeInTheDocument();
  });

  it("keeps portfolio workflow simulated and preview-only", async () => {
    renderPage(<PaperPortfolioLabPage />);
    expect((await screen.findAllByText("SIMULATED / PAPER ONLY")).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: /Preview reference plan/i }));
    expect(await screen.findByText(/APPROVED_FOR_SIMULATION/)).toBeInTheDocument();
    expect(screen.getByText(/brokerage_connectivity/)).toBeInTheDocument();
  });
});
