import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api";
import { AnalyticsComparison } from "../pages/AnalyticsComparison";
import { OptionalEngineStatus } from "../pages/OptionalEngineStatus";
import { OptimizationExperiment } from "../pages/OptimizationExperiment";
import { SecFilings } from "../pages/SecFilings";
import { UpstreamIntegrations } from "../pages/UpstreamIntegrations";
import { UpstreamLicenseInventory } from "../pages/UpstreamLicenseInventory";
import { renderPage } from "./render";

vi.mock("../api", () => ({ api: {
  secFilings: vi.fn(), importSecFixture: vi.fn(), analyticsComparison: vi.fn(),
  optimizationExperiment: vi.fn(), upstreamIntegrations: vi.fn(), upstreamLicenses: vi.fn(),
  leanStatus: vi.fn(), leanFixture: vi.fn(),
} }));
const mocked = vi.mocked(api);

beforeEach(() => {
  vi.clearAllMocks();
  mocked.secFilings.mockResolvedValue({ total: 1, items: [{
    id: "filing-1", company_id: "company-1", company_name: "Example Technology Inc.",
    cik: "0000320193", accession_number: "0000320193-26-000001", form_type: "10-K",
    filing_date: "2026-02-01", accepted_at: "2026-02-01T21:15:00Z",
    reporting_period: "2025-12-31", source_url: "https://www.sec.gov/fixture",
    retrieved_at: "2026-03-01T12:00:00Z", content_checksum: "abc",
    raw_document_reference: "fixture://sec", parser_version: "1.0",
    edgartools_version: "5.43.1-fixture", is_amendment: false,
    simulation_eligible_at: "2026-02-01T21:15:00Z",
  }] });
  mocked.importSecFixture.mockResolvedValue({ status: "completed" });
  mocked.analyticsComparison.mockResolvedValue({
    id: "analytics-1", canonical_metrics: { sharpe: 1 }, quantstats_metrics: { sharpe: 1 },
    reconciliation: [{ metric: "sharpe", absolute_difference: 0, agreement_status: "agrees", methodology_note: "Daily return-series methodology" }],
    agreement_status: "agrees", engine_versions: { canonical: "0.6.0", quantstats: "0.0.81-fixture" }, return_series_checksum: "abc",
  });
  mocked.optimizationExperiment.mockResolvedValue({
    id: "opt-1", model: "minimum_variance", asset_universe: ["AAPL", "SPY"],
    weights: { AAPL: 0.4, SPY: 0.6 }, objective_values: {}, risk_metrics: {},
    constraints: { allow_short: false }, optimizer_version: "0.20.1-fixture", warnings: [],
  });
  const health = { status: "fixture_only", available: true, message: "fixture-tested", version: { project: "example", adapter_version: "1", library_version: null, source_commit: null }, capabilities: [{ code: "fixture", description: "Fixture", fixture_tested: true, live_verified: false }] };
  mocked.upstreamIntegrations.mockResolvedValue({ contains_secrets: false, items: { edgartools: health, lean: { ...health, available: false, status: "disabled" } } });
  mocked.upstreamLicenses.mockResolvedValue({ policy_version: "1.0", contains_source_code: false, items: [{
    name: "OpenBB-finance/OpenBB", repository_url: "https://github.com/OpenBB-finance/OpenBB",
    reviewed_revision: "1234567890abcdef", reviewed_release: "ODP", license: "AGPL-3.0-only",
    integration_category: "reference_only", approved_use: "Public behavior study",
    prohibited_use: "No copied code", dependency_version: null, maintenance_status: "reference_only",
    security_status: "Not installed", commercial_use_status: "Reference only",
  }] });
  mocked.leanStatus.mockResolvedValue({ ...health, available: false, status: "disabled" });
  mocked.leanFixture.mockResolvedValue({ status: "fixture_completed", comparison: { difference: "2.50" } });
});

describe("Sprint 6 upstream integration workflows", () => {
  it("loads and labels deterministic SEC filings", async () => {
    renderPage(<SecFilings />);
    expect(await screen.findByText("0000320193-26-000001")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Load deterministic fixture filings" }));
    expect(await screen.findByText(/without network access/)).toBeInTheDocument();
  });
  it("runs analytics reconciliation and constrained optimization", async () => {
    const { unmount } = renderPage(<AnalyticsComparison />);
    await userEvent.click(screen.getByRole("button", { name: "Run analytics comparison" }));
    expect(await screen.findByText("Daily return-series methodology")).toBeInTheDocument();
    unmount();
    renderPage(<OptimizationExperiment />);
    await userEvent.click(screen.getByRole("button", { name: "Run deterministic optimization" }));
    expect(await screen.findByText("60.00%")).toBeInTheDocument();
    expect(screen.getByText(/No shorting/)).toBeInTheDocument();
  });
  it("shows adapter, reference-only, fixture/live, and unavailable labels", async () => {
    const { unmount } = renderPage(<UpstreamIntegrations />);
    expect(await screen.findByText(/optional dependency unavailable/)).toBeInTheDocument();
    expect(screen.getAllByText(/not live-verified/).length).toBeGreaterThan(0);
    unmount();
    renderPage(<UpstreamLicenseInventory />);
    expect(await screen.findByText("reference_only")).toBeInTheDocument();
    expect(screen.getByText("AGPL-3.0-only")).toBeInTheDocument();
    unmount();
    renderPage(<OptionalEngineStatus />);
    expect(await screen.findByText(/No live mode/)).toBeInTheDocument();
  });
});
