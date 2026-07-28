export interface PageInfo { page: number; page_size: number; total: number; pages: number }

export interface Asset {
  id: string;
  symbol: string;
  name: string;
  asset_type: string;
  exchange: string;
  currency: string;
  sector: string | null;
  industry: string | null;
  is_active: boolean;
  latest_price: string | null;
  latest_price_time: string | null;
  is_demonstration_data: boolean | null;
}

export interface AssetPage { items: Asset[]; pagination: PageInfo }

export interface PriceBar {
  id: string;
  interval: string;
  event_time: string;
  publication_time: string;
  effective_time: string;
  retrieval_time: string;
  open: string;
  high: string;
  low: string;
  close: string;
  adjusted_close: string;
  volume: number;
  data_source_id: string;
  source_name: string;
  is_demonstration_data: boolean;
}

export interface PricePage { symbol: string; items: PriceBar[]; pagination: PageInfo }

export interface WatchlistAsset {
  symbol: string;
  name: string;
  added_at: string;
  latest_price: string | null;
  latest_price_time: string | null;
  is_demonstration_data: boolean | null;
}

export interface Watchlist {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
  assets: WatchlistAsset[];
}

export interface SystemInfo {
  app_name: string;
  version: string;
  environment: string;
  database_engine: string;
  demonstration_mode: boolean;
  database_health: string;
  tracked_assets: number;
  watchlists: number;
  demonstration_bars: number;
  warning: string;
}

export interface DataSource {
  id: string;
  name: string;
  provider_type: string;
  is_enabled: boolean;
  health: string;
  last_successful_retrieval: string | null;
  stored_records: number;
  freshness_status: string;
  license_notes: string;
}
