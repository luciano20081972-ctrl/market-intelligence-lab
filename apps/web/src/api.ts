import type { Asset, AssetPage, DataSource, PricePage, SystemInfo, Watchlist } from "./types";

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
};
