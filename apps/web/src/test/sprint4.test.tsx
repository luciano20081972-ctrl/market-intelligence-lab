import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api";
import { ImportJobDetail } from "../pages/ImportJobDetail";
import { ImportJobs } from "../pages/ImportJobs";
import { Operations } from "../pages/Operations";
import { ProviderDetail } from "../pages/ProviderDetail";
import { Reconciliation } from "../pages/Reconciliation";
import { Schedules } from "../pages/Schedules";
import type { ImportJob, Provider } from "../types";
import { renderPage } from "./render";

vi.mock("../api", () => ({ api: {
  provider: vi.fn(), providerStatus: vi.fn(), testProvider: vi.fn(), providers: vi.fn(),
  importJobs: vi.fn(), previewImport: vi.fn(), createImportJob: vi.fn(), importJob: vi.fn(),
  importJobEvents: vi.fn(), importJobQuality: vi.fn(), cancelImportJob: vi.fn(), retryImportJob: vi.fn(),
  operationQueue: vi.fn(), operationWorkers: vi.fn(), operationHealth: vi.fn(), recoverAbandoned: vi.fn(),
  operationsCenter: vi.fn(), freshnessStatuses: vi.fn(), operationalAlerts: vi.fn(), scheduledTasks: vi.fn(),
  schedules: vi.fn(), createSchedule: vi.fn(), updateSchedule: vi.fn(), runScheduleNow: vi.fn(), deleteSchedule: vi.fn(),
  reconciliationPreview: vi.fn(), reconciliationRun: vi.fn(), reconciliationReports: vi.fn(),
} }));

const mocked = vi.mocked(api);
const provider: Provider = {
  id: "provider-stooq", code: "stooq", name: "Stooq Historical Daily Data",
  capabilities: ["historical_ohlcv", "asset_metadata"], credential_environment_keys: [],
  is_enabled: true, health: "healthy", last_tested_at: null,
  last_successful_import_at: null, adapter_type: "StooqAdapter",
  authentication_required: false, configuration_status: "configured",
};
const job: ImportJob = {
  id: "job-1", provider_id: provider.id, provider_code: provider.code, mode: "incremental",
  status: "failed", symbols: ["AAPL"], requested_at: "2026-07-29T12:00:00Z",
  started_at: "2026-07-29T12:00:01Z", completed_at: "2026-07-29T12:00:02Z",
  next_retry_at: null, attempt: 1, max_attempts: 3, records_processed: 0,
  records_inserted: 0, records_skipped: 0, processing_duration_ms: 100,
  error_summary: "temporary failure", validation_report: {}, resume_cursor: {}, dry_run: false,
  adjustment_preference: "provider_default", queue_name: "manual", batches: [],
};

beforeEach(() => {
  vi.clearAllMocks();
  mocked.provider.mockResolvedValue(provider);
  mocked.providerStatus.mockResolvedValue({ provider_id: provider.id, code: provider.code, configured: true, health: "healthy", connectivity: "not_tested", last_checked_at: null, last_successful_import_at: null, stale: true, authentication_required: false, rate_limit: { requests_remaining: null, reset_at: null, events: 0 } });
  mocked.testProvider.mockResolvedValue({
    status: "healthy", connectivity: "connected", response_classification: "valid_csv",
    schema_compatible: true, message: "Stooq returned compatible daily OHLCV data",
  });
  mocked.providers.mockResolvedValue({ items: [provider], meta: { page: 1, page_size: 100, total: 1 } });
  mocked.importJobs.mockResolvedValue({ items: [], meta: { page: 1, page_size: 100, total: 0 } });
  mocked.previewImport.mockResolvedValue({ provider: "stooq", mode: "incremental", dry_run: true, adjustment_preference: "provider_default", can_submit: true, reports: [{ symbol: "AAPL", provider_symbol: "aapl.us", records: 5, valid: true }] });
  mocked.createImportJob.mockResolvedValue({ ...job, status: "queued" });
  mocked.importJob.mockResolvedValue(job);
  mocked.importJobEvents.mockResolvedValue([{ id: "event-1", event_type: "attempt_finished", from_status: "running", to_status: "failed", message: "temporary failure", details: {}, created_at: "2026-07-29T12:00:02Z" }]);
  mocked.importJobQuality.mockResolvedValue({ job_id: job.id, status: job.status, report: { issue_count: 1 } });
  mocked.retryImportJob.mockResolvedValue({ id: job.id, status: "queued" });
  mocked.cancelImportJob.mockResolvedValue({ ...job, status: "cancelled" });
  mocked.operationQueue.mockResolvedValue({ depth: 2, failed: 1, running: 0, by_status: { queued: 2, failed: 1 } });
  mocked.operationWorkers.mockResolvedValue({ items: [], meta: { page: 1, page_size: 25, total: 0 } });
  mocked.operationHealth.mockResolvedValue({ status: "degraded" });
  mocked.operationsCenter.mockResolvedValue({ overall: "DEGRADED", categories: { application: "HEALTHY", database: "HEALTHY", workers: "ACTION_NEEDED", scheduler: "ACTION_NEEDED", data: "HEALTHY", authentication: "HEALTHY", storage: "HEALTHY", backups: "DEGRADED" }, open_alerts: 0, stale_datasets: 0, maintenance: { enabled: false, reason: null }, latest_backup: null });
  mocked.freshnessStatuses.mockResolvedValue([]);
  mocked.operationalAlerts.mockResolvedValue([]);
  mocked.scheduledTasks.mockResolvedValue([]);
  mocked.recoverAbandoned.mockResolvedValue({ count: 1, recovered_job_ids: [job.id] });
  mocked.schedules.mockResolvedValue([]);
  mocked.createSchedule.mockResolvedValue({ id: "schedule-1", provider_id: provider.id, name: "Daily AAPL", symbols: ["AAPL"], mode: "incremental", adjustment_preference: "provider_default", timezone: "America/New_York", is_enabled: true, next_run_at: "2026-07-30T12:00:00Z", last_run_at: null, failure_count: 0, last_error: null, date_range_policy: { lookback_days: 7 } });
  mocked.reconciliationReports.mockResolvedValue([]);
  mocked.reconciliationPreview.mockResolvedValue({ dry_run: true, records_checked: 10, issue_count: 1, conflict_count: 0, issues: [{ type: "stale_latest_bar", severity: "warning", record: "AAPL" }] });
  mocked.reconciliationRun.mockResolvedValue({ id: "recon-1", status: "succeeded", dry_run: false, records_checked: 10, issue_count: 1 });
});

describe("Sprint 4 real market-data operations", () => {
  it("shows provider status and runs a connection test", async () => {
    renderPage(<ProviderDetail />, "/providers/provider-stooq", "/providers/:id");
    expect(await screen.findByText("Stooq Historical Daily Data")).toBeInTheDocument();
    expect(screen.getByText("No API key required")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Test connection" }));
    await waitFor(() => expect(mocked.testProvider).toHaveBeenCalledWith(provider.id));
    expect(await screen.findByText("valid_csv")).toBeInTheDocument();
    expect(screen.getByText("Stooq returned compatible daily OHLCV data")).toBeInTheDocument();
  });

  it.each([
    ["reachable invalid HTML", "degraded", "reachable_invalid", "html_access_page", "Stooq returned an HTML verification or access page instead of market data"],
    ["unavailable network", "unavailable", "unavailable", "network_unavailable", "Stooq request timed out or could not be reached"],
    ["schema mismatch", "degraded", "reachable_invalid", "schema_mismatch", "Stooq CSV columns were missing or malformed"],
    ["no data", "degraded", "reachable_no_data", "no_data", "Stooq returned no data for the bounded request"],
  ])("renders the %s provider diagnostic safely", async (_name, status, connectivity, classification, message) => {
    mocked.testProvider.mockResolvedValue({
      status, connectivity, response_classification: classification,
      schema_compatible: classification === "no_data", message,
    });
    renderPage(<ProviderDetail />, "/providers/provider-stooq", "/providers/:id");
    await userEvent.click(await screen.findByRole("button", { name: "Test connection" }));
    expect(await screen.findByText(classification)).toBeInTheDocument();
    expect(screen.getByText(message)).toBeInTheDocument();
    expect(screen.queryByText(/<!doctype|captcha|cloudflare/i)).not.toBeInTheDocument();
  });

  it("previews and submits a durable import", async () => {
    renderPage(<ImportJobs />, "/imports");
    await screen.findByText("No import history");
    await userEvent.click(screen.getByRole("button", { name: "Preview import" }));
    expect(await screen.findByText("Preview passed")).toBeInTheDocument();
    expect(screen.getByText(/aapl.us/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Queue import" }));
    await waitFor(() => expect(mocked.createImportJob).toHaveBeenCalled());
    expect(mocked.createImportJob.mock.calls[0]?.[0]).toMatchObject({ execute_immediately: false });
  });

  it("prevents an external import when preflight validation fails", async () => {
    mocked.previewImport.mockResolvedValue({
      provider: "stooq", mode: "incremental", dry_run: true,
      adjustment_preference: "provider_default", can_submit: false,
      reports: [{
        symbol: "AAPL", records: 0, valid: false,
        error: "Stooq returned an HTML verification or access page instead of market data",
      }],
    });
    renderPage(<ImportJobs />, "/imports");
    const queue = await screen.findByRole("button", { name: "Queue import" });
    expect(queue).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Preview import" }));
    expect(await screen.findByText("Preview found issues")).toBeInTheDocument();
    expect(queue).toBeDisabled();
    await userEvent.click(queue);
    expect(mocked.createImportJob).not.toHaveBeenCalled();
  });

  it("renders queue state, worker empty state, and recovery", async () => {
    renderPage(<Operations />, "/operations");
    expect(await screen.findByText("No worker registered")).toBeInTheDocument();
    expect(screen.getAllByText("2")).toHaveLength(2);
    await userEvent.click(screen.getByRole("button", { name: "Recover abandoned jobs" }));
    expect(await screen.findByText("Recovered 1 abandoned job(s).")).toBeInTheDocument();
  });

  it("creates a validated daily schedule", async () => {
    renderPage(<Schedules />, "/schedules");
    expect(await screen.findByText("No schedules")).toBeInTheDocument();
    await userEvent.clear(screen.getByLabelText("Schedule timezone"));
    await userEvent.type(screen.getByLabelText("Schedule timezone"), "UTC");
    await userEvent.click(screen.getByRole("button", { name: "Create daily schedule" }));
    await waitFor(() => expect(mocked.createSchedule).toHaveBeenCalled());
    expect(mocked.createSchedule.mock.calls[0]?.[0]).toMatchObject({ timezone: "UTC", symbols: ["AAPL"] });
  });

  it("displays reconciliation findings and report empty state", async () => {
    renderPage(<Reconciliation />, "/reconciliation");
    expect(await screen.findByText("No reconciliation reports")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Dry-run preview" }));
    expect(await screen.findByText("stale_latest_bar")).toBeInTheDocument();
    expect(screen.getByText("AAPL")).toBeInTheDocument();
  });

  it("shows a job timeline and retries a failed job", async () => {
    renderPage(<ImportJobDetail />, "/imports/job-1", "/imports/:id");
    expect(await screen.findByText("attempt_finished")).toBeInTheDocument();
    expect(screen.getByText(/issue_count/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(mocked.retryImportJob).toHaveBeenCalledWith(job.id));
  });

  it("cancels a queued job", async () => {
    mocked.importJob.mockResolvedValue({ ...job, status: "queued", error_summary: null });
    renderPage(<ImportJobDetail />, "/imports/job-1", "/imports/:id");
    await screen.findByText("stooq · queued");
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    await waitFor(() => expect(mocked.cancelImportJob).toHaveBeenCalledWith(job.id));
  });
});
