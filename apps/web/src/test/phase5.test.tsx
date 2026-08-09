import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api";
import { ComputeDashboard } from "../pages/ComputeDashboard";
import { ComputeJobDetail } from "../pages/ComputeJobDetail";
import { MarketControlStatus } from "../pages/MarketControlStatus";
import { renderPage } from "./render";

vi.mock("../api", () => ({ api: {
  computeStatus: vi.fn(), computeJobs: vi.fn(), computeJob: vi.fn(),
  cancelComputeJob: vi.fn(), retryComputeJob: vi.fn(), cloudBudget: vi.fn(), marketControlStatus: vi.fn(),
  decisionSignals: vi.fn(), alertEvents: vi.fn(),
} }));
const mocked = vi.mocked(api);
const job = {
  id: "job-1", submission_key: "fixture-heavy", job_type: "factor_sweep",
  job_class: "HEAVY", state: "CLOUD_DISABLED", priority: 50, selected_provider: null,
  estimate: { cpu: "2.000", ram_mb: 2048, runtime_seconds: 120,
    estimated_cost_usd: "0.020000", task_count: 1 },
  attempt_count: 0, max_attempts: 3, symbols: ["AAPL"], input_manifest_hash: "a".repeat(64),
  result_manifest: {}, error_classification: null, error_detail: null,
  created_at: "2026-08-09T00:00:00Z", started_at: null, completed_at: null,
  updated_at: "2026-08-09T00:00:00Z",
};

beforeEach(() => {
  vi.clearAllMocks();
  mocked.computeStatus.mockResolvedValue({ cloud_enabled: false, cloud_configured: false,
    providers: { local: "available", cloud_run: "disabled" }, resource_guard: {
      available_ram_mb: 2800, load_per_cpu: 0.12, running_analytical_jobs: 0 },
    job_counts: { CLOUD_DISABLED: 1 } });
  mocked.computeJobs.mockResolvedValue([job]);
  mocked.computeJob.mockResolvedValue(job);
  mocked.cloudBudget.mockResolvedValue({ cloud_enabled: false, spend_cap_blocked: false,
    limits: { job_usd: "0.25", daily_usd: "0.50", monthly_usd: "5.00",
      parallel_tasks: 1, runtime_seconds: 900 },
    usage: { daily_usd: "0", monthly_usd: "0", active_tasks: 0 } });
  mocked.marketControlStatus.mockResolvedValue({ supervisor: { status: "healthy",
    instance_id: "mil-supervisor", heartbeat_at: "2026-08-09T00:00:00Z",
    session_state: "CLOSED", last_signal_scan_at: null,
    providers: { local: "available", cloud_run: "disabled" }, last_error: null },
    freshness_last_two_minutes: { STALE: 1 } });
  mocked.decisionSignals.mockResolvedValue([]);
  mocked.alertEvents.mockResolvedValue([]);
});

describe("Phase 5 control-plane pages", () => {
  it("explains cloud-disabled heavy jobs and estimated budget limits", async () => {
    renderPage(<ComputeDashboard />);
    expect(await screen.findByText("Cloud disabled")).toBeInTheDocument();
    expect(screen.getByText("CLOUD_DISABLED")).toBeInTheDocument();
    expect(screen.getByText("$0.020000 · 2048 MiB")).toBeInTheDocument();
    expect(screen.getByText(/provider billing can lag/i)).toBeInTheDocument();
  });

  it("shows routing, retries, cost, and validation detail", async () => {
    renderPage(<ComputeJobDetail />, "/compute/jobs/job-1", "/compute/jobs/:id");
    expect(await screen.findByText("factor_sweep")).toBeInTheDocument();
    expect(screen.getByText("HEAVY")).toBeInTheDocument();
    expect(screen.getByText("0 / 3")).toBeInTheDocument();
    expect(screen.getByText("$0.020000")).toBeInTheDocument();
  });

  it("labels session, freshness, and paper-only safety", async () => {
    renderPage(<MarketControlStatus />);
    expect(await screen.findByText("CLOSED")).toBeInTheDocument();
    expect(screen.getByText("STALE")).toBeInTheDocument();
    expect(screen.getByText(/Decision support only/)).toBeInTheDocument();
  });
});
