import type {
  Asset, AssetPage, Backtest, BacktestPage, BacktestTrade, DataSource, EquityPoint,
  OrderPayload, OrderPreview, PaperFill, PaperOrder, PaperPortfolio, Performance,
  Position, PricePage, RiskRule, StrategyPage, SystemInfo, Watchlist, ProviderPage,
  ImportJob, ImportJobPage, ImportErrorPage, CorporateActionPage, TradingSessionPage,
  ImportPreview, ImportSchedule, JobEvent, Provider, ProviderStatus, QueueSummary,
  ProviderDiagnostic, ReconciliationReport, WorkerPage,
  CurrentUser, WorkspaceSummary, AuditPage, InfrastructureRegistry, ProviderComparison,
  BacktestManifest, BacktestValidation,
  AnalyticsComparisonResult, OptimizationResult, SecCompany, SecFiling,
  SecInsiderTransaction, SecInstitutionalHolding, UpstreamHealth, UpstreamProject,
  WorldDataSource, DataManifestRecord, WorldSeries, WorldObservation,
  CompanyDriverProfile, DataRelevancePage, EconomicEntityPage, EconomicGraph,
  RelationshipEvidence, ResolutionCandidate,
} from "./types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";
let accessToken: string | null = null;
let workspaceId: string | null = null;

export function configureRequestContext(token: string | null, workspace: string | null) {
  accessToken = token;
  workspaceId = workspace;
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const authHeaders: Record<string, string> = {};
  if (accessToken) authHeaders.Authorization = `Bearer ${accessToken}`;
  if (workspaceId) authHeaders["X-Workspace-ID"] = workspaceId;
  const response = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...authHeaders, ...init?.headers },
  });
  if (response.status === 401) window.dispatchEvent(new Event("mil:session-expired"));
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as {
      detail?: string | { message?: string };
    };
    const message = typeof body.detail === "string" ? body.detail : body.detail?.message;
    throw new ApiError(response.status, message ?? `Request failed (${response.status})`);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const api = {
  currentUser: () => request<CurrentUser>("/api/v1/auth/me"),
  authHealth: () => request<{ status: string; mode: string; provider_configured: boolean }>("/api/v1/auth/health"),
  auditAuth: (action: string, result: "success" | "failure") => request<{ recorded: boolean }>("/api/v1/auth/events", { method: "POST", body: JSON.stringify({ action, result }) }),
  updateCurrentUser: (displayName: string) => request<CurrentUser>("/api/v1/users/me", { method: "PATCH", body: JSON.stringify({ display_name: displayName }) }),
  workspaces: () => request<WorkspaceSummary[]>("/api/v1/workspaces"),
  workspace: (id: string) => request<WorkspaceSummary>(`/api/v1/workspaces/${id}`),
  workspaceMembers: (id: string) => request<Array<Record<string, string>>>(`/api/v1/workspaces/${id}/members`),
  inviteMember: (id: string, email: string, role: string) => request<Record<string, string>>(`/api/v1/workspaces/${id}/invitations`, { method: "POST", body: JSON.stringify({ email, role }) }),
  auditEvents: (id: string) => request<AuditPage>(`/api/v1/workspaces/${id}/audit-events`),
  infrastructureServices: () => request<InfrastructureRegistry>("/api/v1/operations/infrastructure-services"),
  providerComparisons: () => request<{ items: ProviderComparison[]; total: number }>("/api/v1/reconciliation/provider-comparisons"),
  createProviderComparison: (payload: Record<string, unknown>) => request<ProviderComparison>("/api/v1/reconciliation/provider-comparisons", { method: "POST", body: JSON.stringify(payload) }),
  resolveProviderComparison: (id: string, resolution: string, reason: string) => request<ProviderComparison>(`/api/v1/reconciliation/provider-comparisons/${id}/resolve`, { method: "POST", body: JSON.stringify({ status: resolution, reason }) }),
  backtestManifest: (id: string) => request<BacktestManifest>(`/api/v1/backtests/${id}/manifest`),
  backtestValidation: (id: string) => request<BacktestValidation>(`/api/v1/backtests/${id}/validation-report`),
  health: () => request<{ status: string; database: string; version: string }>("/health"),
  systemInfo: () => request<SystemInfo>("/api/v1/system/info"),
  dataSources: () => request<DataSource[]>("/api/v1/system/data-sources"),
  assets: (params = "") => request<AssetPage>(`/api/v1/assets${params ? `?${params}` : ""}`),
  asset: (symbol: string) => request<Asset>(`/api/v1/assets/${encodeURIComponent(symbol)}`),
  prices: (symbol: string, params = "page_size=120") =>
    request<PricePage>(`/api/v1/assets/${encodeURIComponent(symbol)}/prices?${params}`),
  watchlists: () => request<Watchlist[]>("/api/v1/watchlists"),
  createWatchlist: (name: string) =>
    request<Watchlist>("/api/v1/watchlists", { method: "POST", body: JSON.stringify({ name }) }),
  renameWatchlist: (id: string, name: string) =>
    request<Watchlist>(`/api/v1/watchlists/${id}`, { method: "PATCH", body: JSON.stringify({ name }) }),
  deleteWatchlist: (id: string) => request<void>(`/api/v1/watchlists/${id}`, { method: "DELETE" }),
  addAsset: (id: string, symbol: string) =>
    request<Watchlist>(`/api/v1/watchlists/${id}/assets`, { method: "POST", body: JSON.stringify({ symbol }) }),
  removeAsset: (id: string, symbol: string) =>
    request<Watchlist>(`/api/v1/watchlists/${id}/assets/${encodeURIComponent(symbol)}`, { method: "DELETE" }),
  strategies: () => request<StrategyPage>("/api/v1/strategies?page_size=100"),
  backtests: () => request<BacktestPage>("/api/v1/backtests?page_size=100"),
  backtest: (id: string) => request<Backtest>(`/api/v1/backtests/${id}`),
  createBacktest: (payload: Record<string, unknown>) => request<Backtest>("/api/v1/backtests", { method: "POST", body: JSON.stringify(payload) }),
  backtestMetrics: (id: string) => request<Record<string, number | string>>(`/api/v1/backtests/${id}/metrics`),
  backtestTrades: (id: string) => request<BacktestTrade[]>(`/api/v1/backtests/${id}/trades`),
  backtestEquity: (id: string) => request<EquityPoint[]>(`/api/v1/backtests/${id}/equity-curve`),
  backtestDrawdown: (id: string) => request<EquityPoint[]>(`/api/v1/backtests/${id}/drawdown`),
  paperPortfolios: () => request<PaperPortfolio[]>("/api/v1/paper-portfolios"),
  paperPortfolio: (id: string) => request<PaperPortfolio>(`/api/v1/paper-portfolios/${id}`),
  createPaperPortfolio: (name: string, startingCash: string) => request<PaperPortfolio>("/api/v1/paper-portfolios", { method: "POST", body: JSON.stringify({ name, starting_cash: startingCash }) }),
  previewOrder: (id: string, payload: OrderPayload) => request<OrderPreview>(`/api/v1/paper-portfolios/${id}/orders/preview`, { method: "POST", body: JSON.stringify(payload) }),
  submitOrder: (id: string, payload: OrderPayload) => request<PaperOrder>(`/api/v1/paper-portfolios/${id}/orders`, { method: "POST", body: JSON.stringify(payload) }),
  paperOrders: (id: string) => request<PaperOrder[]>(`/api/v1/paper-portfolios/${id}/orders`),
  paperFills: (id: string) => request<PaperFill[]>(`/api/v1/paper-portfolios/${id}/fills`),
  paperPositions: (id: string) => request<Position[]>(`/api/v1/paper-portfolios/${id}/positions`),
  paperPerformance: (id: string) => request<Performance>(`/api/v1/paper-portfolios/${id}/performance`),
  cancelOrder: (portfolioId: string, orderId: string) => request<PaperOrder>(`/api/v1/paper-portfolios/${portfolioId}/orders/${orderId}`, { method: "DELETE" }),
  pausePortfolio: (id: string) => request<PaperPortfolio>(`/api/v1/paper-portfolios/${id}/pause`, { method: "POST" }),
  resumePortfolio: (id: string) => request<PaperPortfolio>(`/api/v1/paper-portfolios/${id}/resume`, { method: "POST" }),
  riskRules: (id: string) => request<RiskRule[]>(`/api/v1/paper-portfolios/${id}/risk-rules`),
  updateRiskRule: (portfolioId: string, ruleId: string, limitValue: string, isEnabled: boolean) => request<RiskRule>(`/api/v1/paper-portfolios/${portfolioId}/risk-rules/${ruleId}`, { method: "PATCH", body: JSON.stringify({ limit_value: limitValue, is_enabled: isEnabled }) }),
  providers: () => request<ProviderPage>("/api/v1/providers?page_size=100"),
  provider: (providerId: string) => request<Provider>(`/api/v1/providers/${providerId}`),
  providerStatus: (providerId: string) => request<ProviderStatus>(`/api/v1/providers/${providerId}/status`),
  testProvider: (providerId: string) => request<ProviderDiagnostic>(`/api/v1/providers/${providerId}/test`, { method: "POST" }),
  importJobs: () => request<ImportJobPage>("/api/v1/import/jobs?page_size=100"),
  importJob: (id: string) => request<ImportJob>(`/api/v1/import/jobs/${id}`),
  createImportJob: (payload: Record<string, unknown>) => request<ImportJob>("/api/v1/import/jobs", { method: "POST", body: JSON.stringify(payload) }),
  previewImport: (payload: Record<string, unknown>) => request<ImportPreview>("/api/v1/import/jobs/preview", { method: "POST", body: JSON.stringify(payload) }),
  cancelImportJob: (id: string) => request<ImportJob>(`/api/v1/import/jobs/${id}/cancel`, { method: "POST" }),
  retryImportJob: (id: string) => request<{ id: string; status: string }>(`/api/v1/import/jobs/${id}/retry`, { method: "POST" }),
  restartImportJob: (id: string) => request<ImportJob>(`/api/v1/import/jobs/${id}/restart`, { method: "POST" }),
  importJobEvents: (id: string) => request<JobEvent[]>(`/api/v1/import/jobs/${id}/events`),
  importJobQuality: (id: string) => request<{ job_id: string; status: string; report: Record<string, unknown> }>(`/api/v1/import/jobs/${id}/quality-report`),
  operationQueue: () => request<QueueSummary>("/api/v1/operations/queue"),
  operationWorkers: () => request<WorkerPage>("/api/v1/operations/workers"),
  operationHealth: () => request<Record<string, unknown>>("/api/v1/operations/health"),
  recoverAbandoned: () => request<{ count: number; recovered_job_ids: string[] }>("/api/v1/operations/recover-abandoned", { method: "POST" }),
  schedules: () => request<ImportSchedule[]>("/api/v1/import/schedules"),
  createSchedule: (payload: Record<string, unknown>) => request<ImportSchedule>("/api/v1/import/schedules", { method: "POST", body: JSON.stringify(payload) }),
  updateSchedule: (id: string, payload: Record<string, unknown>) => request<ImportSchedule>(`/api/v1/import/schedules/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteSchedule: (id: string) => request<void>(`/api/v1/import/schedules/${id}`, { method: "DELETE" }),
  runScheduleNow: (id: string) => request<{ job_id: string | null; status: string }>(`/api/v1/import/schedules/${id}/run-now`, { method: "POST" }),
  reconciliationPreview: (payload: Record<string, unknown>) => request<ReconciliationReport>("/api/v1/reconciliation/preview", { method: "POST", body: JSON.stringify(payload) }),
  reconciliationRun: (payload: Record<string, unknown>) => request<ReconciliationReport>("/api/v1/reconciliation/run", { method: "POST", body: JSON.stringify(payload) }),
  reconciliationReports: () => request<ReconciliationReport[]>("/api/v1/reconciliation/reports"),
  importErrors: () => request<ImportErrorPage>("/api/v1/import/errors?page_size=100"),
  corporateActions: () => request<CorporateActionPage>("/api/v1/corporate-actions?page_size=100"),
  exchangeCalendar: () => request<TradingSessionPage>("/api/v1/exchange-calendar?page_size=100"),
  secCompanies: () => request<{ items: SecCompany[]; total: number }>("/api/v1/sec/companies"),
  secFilings: () => request<{ items: SecFiling[]; total: number }>("/api/v1/sec/filings"),
  secFiling: (id: string) => request<SecFiling>(`/api/v1/sec/filings/${id}`),
  secInsiderTransactions: () => request<{ items: SecInsiderTransaction[]; total: number }>("/api/v1/sec/insider-transactions"),
  secInstitutionalHoldings: () => request<{ items: SecInstitutionalHolding[]; total: number }>("/api/v1/sec/institutional-holdings"),
  importSecFixture: () => request<Record<string, unknown>>("/api/v1/sec/imports", {
    method: "POST",
    body: JSON.stringify({ cik: "320193", forms: ["10-K", "4", "13F-HR"], mode: "fixture", idempotency_key: "frontend-sec-fixture-v06" }),
  }),
  analyticsComparison: () => request<AnalyticsComparisonResult>("/api/v1/analytics/compare", {
    method: "POST",
    body: JSON.stringify({
      returns: [0.01, -0.005, 0.007, 0.002, -0.001, 0.004],
      benchmark_returns: [0.005, -0.002, 0.004, 0.001, 0, 0.002],
      period_start: "2026-01-01", period_end: "2026-06-30", benchmark: "SPY",
      tolerance: 0.000001,
    }),
  }),
  optimizationExperiment: () => request<OptimizationResult>("/api/v1/optimization/experiments", {
    method: "POST",
    body: JSON.stringify({
      model: "minimum_variance",
      asset_returns: {
        AAPL: [0.01, -0.005, 0.007, 0.002, -0.001, 0.004],
        SPY: [0.005, -0.002, 0.004, 0.001, 0, 0.002],
      },
      training_start: "2025-01-01", training_end: "2025-09-30",
      validation_start: "2025-10-01", validation_end: "2025-12-31",
    }),
  }),
  upstreamIntegrations: () => request<{ items: Record<string, UpstreamHealth>; contains_secrets: boolean }>("/api/v1/upstream/integrations"),
  upstreamLicenses: () => request<{ items: UpstreamProject[]; policy_version: string; contains_source_code: boolean }>("/api/v1/upstream/licenses"),
  leanStatus: () => request<UpstreamHealth>("/api/v1/upstream/engines/lean"),
  leanFixture: () => request<Record<string, unknown>>("/api/v1/upstream/engines/lean/fixture", {
    method: "POST",
    body: JSON.stringify({
      strategy: "buy_and_hold", symbols: ["AAPL"], start: "2025-01-01", end: "2025-12-31",
      initial_cash: "10000", fee_per_order: "1", slippage_bps: "5", live_mode: false,
    }),
  }),
  worldDataSources: () => request<WorldDataSource[]>("/api/v1/data-sources"),
  worldDataSource: (id: string) => request<WorldDataSource>(`/api/v1/data-sources/${encodeURIComponent(id)}`),
  worldDataSourceHealth: (id: string) => request<Record<string, unknown>>(`/api/v1/data-sources/${encodeURIComponent(id)}/health`),
  dataManifests: () => request<{ items: DataManifestRecord[]; total: number }>("/api/v1/data-manifests"),
  dataManifest: (id: string) => request<DataManifestRecord>(`/api/v1/data-manifests/${id}`),
  macroSeries: () => request<{ items: WorldSeries[]; total: number }>("/api/v1/macro/series"),
  macroObservations: (id: string) => request<{ items: WorldObservation[]; total: number }>(`/api/v1/macro/series/${id}/observations`),
  macroAsOf: (id: string, asOf: string) => request<{ items: WorldObservation[]; total: number; point_in_time_safe: boolean }>(`/api/v1/macro/series/${id}/as-of?as_of=${encodeURIComponent(asOf)}`),
  energySeries: () => request<{ items: WorldSeries[]; total: number }>("/api/v1/energy/series"),
  energyObservations: (id: string) => request<{ items: WorldObservation[]; total: number }>(`/api/v1/energy/series/${id}/observations`),
  economicEntities: (entityType?: string) => request<EconomicEntityPage>(
    `/api/v1/entities${entityType ? `?entity_type=${encodeURIComponent(entityType)}` : ""}`,
  ),
  economicGraph: (companyId: string) => request<EconomicGraph>(
    `/api/v1/companies/${companyId}/driver-paths?max_depth=3&max_nodes=100`,
  ),
  companyDriverProfile: (companyId: string) => request<CompanyDriverProfile>(
    `/api/v1/companies/${companyId}/driver-profile`,
  ),
  relationshipEvidence: (entityId: string) => request<{ items: RelationshipEvidence[]; total: number }>(
    `/api/v1/entities/${entityId}/evidence`,
  ),
  dataRelevance: (companyId: string) => request<DataRelevancePage>(
    `/api/v1/companies/${companyId}/data-relevance`,
  ),
  resolutionCandidates: () => request<{ items: ResolutionCandidate[]; total: number }>(
    "/api/v1/entity-resolution/candidates?status=candidate",
  ),
  decideResolution: (id: string, decision: "confirm" | "reject", reason: string) =>
    request<{ id: string; candidate_id: string; decision: string }>(
      `/api/v1/entity-resolution/${id}/${decision}`,
      { method: "POST", body: JSON.stringify({ reason }) },
    ),
};
