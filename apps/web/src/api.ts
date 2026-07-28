import type {
  Asset, AssetPage, Backtest, BacktestPage, BacktestTrade, DataSource, EquityPoint,
  OrderPayload, OrderPreview, PaperFill, PaperOrder, PaperPortfolio, Performance,
  Position, PricePage, RiskRule, StrategyPage, SystemInfo, Watchlist,
} from "./types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as { detail?: string };
    throw new ApiError(response.status, body.detail ?? `Request failed (${response.status})`);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const api = {
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
};
