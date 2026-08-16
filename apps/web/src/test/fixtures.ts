import type { Asset, PriceBar, SystemInfo, Watchlist } from "../types";

export const systemInfo: SystemInfo = {
  app_name: "Market Intelligence Lab", version: "0.14.1", environment: "test",
  database_engine: "sqlite", demonstration_mode: true, database_health: "healthy",
  tracked_assets: 9, watchlists: 0, demonstration_bars: 1080,
  warning: "Synthetic demonstration data — not live market data.",
};

export const asset: Asset = {
  id: "asset-1", symbol: "AAPL", name: "Apple Inc.", asset_type: "Stock",
  exchange: "NASDAQ", currency: "USD", sector: "Technology", industry: "Consumer Electronics",
  is_active: true, latest_price: "201.25", latest_price_time: "2025-06-18T21:00:00Z",
  is_demonstration_data: true,
};

export const bar: PriceBar = {
  id: "bar-1", interval: "1d", event_time: "2025-06-18T21:00:00Z",
  publication_time: "2025-06-18T21:10:00Z", effective_time: "2025-06-18T21:00:00Z",
  retrieval_time: "2025-06-19T02:00:00Z", open: "200.00", high: "203.00", low: "199.00",
  close: "201.25", adjusted_close: "201.25", volume: 1000000, data_source_id: "source-1",
  source_name: "Deterministic Synthetic Demonstration Provider", is_demonstration_data: true,
};

export const watchlist: Watchlist = {
  id: "watch-1", name: "Core", description: null, created_at: "2025-01-01T00:00:00Z",
  updated_at: "2025-01-01T00:00:00Z", assets: [],
};
