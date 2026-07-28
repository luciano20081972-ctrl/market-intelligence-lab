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

export interface StrategyVersion {
  id: string; version: number; parameters: Record<string, unknown>;
  parameter_schema: Record<string, unknown>; calculation_notes: string; created_at: string;
}
export interface Strategy {
  id: string; name: string; strategy_type: string; description: string;
  is_builtin: boolean; latest_version: StrategyVersion; versions: StrategyVersion[];
}
export interface StrategyPage { items: Strategy[]; page: number; page_size: number; total: number }

export interface Backtest {
  id: string; strategy_version_id: string; strategy_name: string; strategy_type: string;
  status: string; asset_symbols: string[]; benchmark_symbol: string; start_time: string;
  end_time: string; initial_cash: string; final_equity: string; cash_balance: string;
  metrics: Record<string, number | string>; strategy_configuration: Record<string, unknown>;
  risk_configuration: Record<string, unknown>; execution_assumptions: Record<string, unknown>;
  data_source_identifiers: string[]; application_version: string; is_hypothetical: boolean;
  created_at: string;
}
export interface BacktestPage { items: Backtest[]; page: number; page_size: number; total: number }
export interface BacktestTrade {
  id: string; symbol: string; side: string; signal_time: string; execution_time: string;
  quantity: string; price: string; gross_value: string; fees: string; cash_after: string;
  reason: string; source_price_bar_id: string;
}
export interface EquityPoint {
  event_time: string; equity: string; benchmark_value: string; cash: string;
  exposure: string; drawdown: string; cumulative_fees: string;
}

export interface Position {
  id: string; symbol: string; name: string; sector: string | null; quantity: string;
  average_cost: string; mark_price: string | null; market_value: string;
  realized_pnl: string; unrealized_pnl: string;
}
export interface PaperPortfolio {
  id: string; name: string; currency: string; starting_cash: string; cash_balance: string;
  portfolio_value: string; realized_pnl: string; unrealized_pnl: string; exposure: string;
  status: string; positions: Position[]; open_order_count: number; created_at: string;
  updated_at: string; warning: string;
}
export interface PaperOrder {
  id: string; client_order_id: string; symbol: string; side: string; order_type: string;
  quantity: string; limit_price: string | null; stop_price: string | null; status: string;
  is_triggered: boolean; rejection_reason: string | null; estimated_value: string | null;
  estimated_fees: string | null; submitted_at: string; cancelled_at: string | null;
  idempotent_replay: boolean;
}
export interface OrderPayload {
  client_order_id: string; symbol: string; side: "buy" | "sell";
  order_type: "market" | "limit" | "stop" | "stop_limit"; quantity: string;
  limit_price?: string; stop_price?: string;
}
export interface OrderPreview {
  outcome: string; estimated_price: string | null; estimated_value: string | null;
  estimated_fees: string; rejection_reasons: string[]; source_price_bar_id: string;
  assumptions: Record<string, string>; is_triggered: boolean;
}
export interface PaperFill {
  id: string; order_id: string; symbol: string; side: string; quantity: string;
  price: string; gross_value: string; fees: string; filled_at: string; source_price_bar_id: string;
}
export interface RiskRule {
  id: string; rule_type: string; limit_value: string; is_enabled: boolean;
  configuration: Record<string, unknown>;
}
export interface Performance {
  portfolio_id: string; starting_cash: string; current_value: string; total_return: string;
  realized_pnl: string; unrealized_pnl: string; points: Array<Record<string, string>>; warning: string;
}
