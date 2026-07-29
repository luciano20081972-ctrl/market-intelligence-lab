import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api";
import { CorporateActions } from "../pages/CorporateActions";
import { DataQuality } from "../pages/DataQuality";
import { ExchangeCalendar } from "../pages/ExchangeCalendar";
import { ImportJobDetail } from "../pages/ImportJobDetail";
import { ImportJobs } from "../pages/ImportJobs";
import { Providers } from "../pages/Providers";
import type { ImportJob, Provider } from "../types";
import { renderPage } from "./render";

vi.mock("../api", () => ({ api: {
  providers: vi.fn(), testProvider: vi.fn(), importJobs: vi.fn(), importJob: vi.fn(),
  createImportJob: vi.fn(), previewImport: vi.fn(), cancelImportJob: vi.fn(),
  retryImportJob: vi.fn(), importJobEvents: vi.fn(), importJobQuality: vi.fn(),
  importErrors: vi.fn(), corporateActions: vi.fn(), exchangeCalendar: vi.fn(),
} }));

const mocked = vi.mocked(api);
const provider: Provider = {
  id: "provider-1", code: "synthetic", name: "Deterministic Synthetic Provider",
  capabilities: ["historical_ohlcv", "corporate_actions"], credential_environment_keys: [],
  is_enabled: true, health: "healthy", last_tested_at: null,
  last_successful_import_at: "2026-07-28T12:00:00Z",
  adapter_type: "SyntheticHistoricalAdapter", authentication_required: false,
  configuration_status: "configured",
};
const job: ImportJob = {
  id: "job-1", provider_id: provider.id, provider_code: provider.code, mode: "incremental",
  status: "succeeded", symbols: ["AAPL"], requested_at: "2026-07-28T12:00:00Z",
  started_at: "2026-07-28T12:00:01Z", completed_at: "2026-07-28T12:00:02Z",
  next_retry_at: null, attempt: 1, max_attempts: 3, records_processed: 5,
  records_inserted: 5, records_skipped: 0, processing_duration_ms: 250,
  error_summary: null, validation_report: { batches: [{ symbol: "AAPL", valid: true, error_count: 0, warning_count: 0 }] },
  resume_cursor: { symbol_index: 1 }, dry_run: false,
  adjustment_preference: "unadjusted", queue_name: "manual",
  batches: [{ id: "batch-1", sequence: 0, status: "succeeded", records_processed: 5, records_inserted: 5, records_skipped: 0, checksum: "abcdef1234567890", validation_report: {} }],
};

beforeEach(() => {
  vi.clearAllMocks();
  mocked.providers.mockResolvedValue({ items: [provider], meta: { page: 1, page_size: 100, total: 1 } });
  mocked.testProvider.mockResolvedValue({ status: "healthy" });
  mocked.importJobs.mockResolvedValue({ items: [job], meta: { page: 1, page_size: 100, total: 1 } });
  mocked.importJob.mockResolvedValue(job);
  mocked.createImportJob.mockResolvedValue(job);
  mocked.cancelImportJob.mockResolvedValue({ ...job, status: "cancelled" });
  mocked.retryImportJob.mockResolvedValue({ id: job.id, status: "queued" });
  mocked.importJobEvents.mockResolvedValue([{ id: "event-1", event_type: "completed", from_status: "running", to_status: "succeeded", message: "Import attempt finished", details: {}, created_at: "2026-07-28T12:00:02Z" }]);
  mocked.importJobQuality.mockResolvedValue({ job_id: job.id, status: job.status, report: {} });
  mocked.importErrors.mockResolvedValue({ items: [], meta: { page: 1, page_size: 100, total: 0 } });
  mocked.corporateActions.mockResolvedValue({ items: [], meta: { page: 1, page_size: 100, total: 0 } });
  mocked.exchangeCalendar.mockResolvedValue({ items: [{ id: "session-1", calendar_code: "XNYS", timezone: "America/New_York", session_date: "2026-07-28", open_time: "2026-07-28T13:30:00Z", close_time: "2026-07-28T20:00:00Z", is_early_close: false, status: "open" }], meta: { page: 1, page_size: 100, total: 1 } });
});

describe("Sprint 3 market-data workflows", () => {
  it("shows provider health and runs a safe provider test", async () => {
    renderPage(<Providers />, "/providers");
    expect(await screen.findByText("Deterministic Synthetic Provider")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Test provider" }));
    await waitFor(() => expect(mocked.testProvider).toHaveBeenCalledWith("provider-1"));
  });

  it("creates an incremental import job", async () => {
    renderPage(<ImportJobs />, "/imports");
    expect(await screen.findByText("5 inserted · 0 skipped")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Queue import" }));
    await waitFor(() => expect(mocked.createImportJob).toHaveBeenCalled());
    expect(mocked.createImportJob.mock.calls[0]?.[0]).toMatchObject({ provider_code: "synthetic", mode: "incremental" });
  });

  it("renders durable import batch provenance", async () => {
    renderPage(<ImportJobDetail />, "/imports/job-1", "/imports/:id");
    expect(await screen.findByText("abcdef123456")).toBeInTheDocument();
    expect(screen.getByText("250 ms")).toBeInTheDocument();
  });

  it("summarizes quality and empty failure state", async () => {
    renderPage(<DataQuality />, "/data-quality");
    expect(await screen.findByText("No validation errors")).toBeInTheDocument();
    expect(screen.getByText("Validation failures")).toBeInTheDocument();
  });

  it("shows corporate-action empty state", async () => {
    renderPage(<CorporateActions />, "/corporate-actions");
    expect(await screen.findByText("No corporate actions")).toBeInTheDocument();
  });

  it("renders timezone-aware exchange sessions", async () => {
    renderPage(<ExchangeCalendar />, "/exchange-calendar");
    expect(await screen.findByText("2026-07-28")).toBeInTheDocument();
    expect(screen.getByText("America/New_York")).toBeInTheDocument();
  });
});
