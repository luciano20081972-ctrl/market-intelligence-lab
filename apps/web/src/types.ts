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
  data_classification?: string; provider_identifiers?: string[];
  import_job_identifiers?: string[]; adjustment_statuses?: string[]; calendar_code?: string;
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

export interface PageMeta { page: number; page_size: number; total: number; }
export interface Provider {
  id: string; code: string; name: string; capabilities: string[];
  credential_environment_keys: string[]; is_enabled: boolean; health: string;
  last_tested_at: string | null; last_successful_import_at: string | null;
  adapter_type: string; authentication_required: boolean; configuration_status: string;
}
export interface ProviderPage { items: Provider[]; meta: PageMeta; }
export interface ImportBatch {
  id: string; sequence: number; status: string; records_processed: number;
  records_inserted: number; records_skipped: number; checksum: string;
  validation_report: Record<string, unknown>;
}
export interface ImportJob {
  id: string; provider_id: string; provider_code: string; mode: string; status: string;
  symbols: string[]; requested_at: string; started_at: string | null; completed_at: string | null;
  next_retry_at: string | null; attempt: number; max_attempts: number;
  records_processed: number; records_inserted: number; records_skipped: number;
  processing_duration_ms: number; error_summary: string | null;
  validation_report: { batches?: Array<{ symbol: string; valid: boolean; error_count: number; warning_count: number }> };
  resume_cursor: Record<string, unknown>; dry_run: boolean; adjustment_preference: string;
  queue_name: string;
  batches: ImportBatch[];
}
export interface ImportJobPage { items: ImportJob[]; meta: PageMeta; }
export interface ImportErrorRecord {
  id: string; job_id: string; batch_id: string | null; error_code: string; message: string;
  record_identifier: string | null; is_retryable: boolean; occurred_at: string;
}
export interface ImportErrorPage { items: ImportErrorRecord[]; meta: PageMeta; }
export interface CorporateAction {
  id: string; symbol: string; provider_code: string; action_type: string;
  effective_time: string; publication_time: string; ratio: string | null; amount: string | null;
  currency: string | null; old_symbol: string | null; new_symbol: string | null;
  adjustment_status: string;
}
export interface CorporateActionPage { items: CorporateAction[]; meta: PageMeta; }
export interface TradingSession {
  id: string; calendar_code: string; timezone: string; session_date: string;
  open_time: string; close_time: string; is_early_close: boolean; status: string;
}
export interface TradingSessionPage { items: TradingSession[]; meta: PageMeta; }

export interface ProviderStatus {
  provider_id: string; code: string; configured: boolean; health: string; connectivity: string;
  response_classification?: string | null; message?: string | null;
  reachable?: boolean | null; valid_response?: boolean | null;
  schema_compatible?: boolean | null; data_available?: boolean | null;
  last_checked_at: string | null; last_successful_import_at: string | null; stale: boolean;
  authentication_required: boolean;
  rate_limit: { requests_remaining: number | null; reset_at: string | null; events: number };
}
export interface ProviderDiagnostic {
  status: string; connectivity?: string; response_classification?: string;
  message?: string; reachable?: boolean; valid_response?: boolean;
  schema_compatible?: boolean; data_available?: boolean;
}
export interface ImportPreview {
  provider: string; mode: string; dry_run: boolean; adjustment_preference: string;
  can_submit: boolean; reports: Array<{ symbol: string; provider_symbol?: string; records: number; valid: boolean; issues?: Array<Record<string, unknown>>; error?: string }>;
}
export interface JobEvent {
  id: string; event_type: string; from_status: string | null; to_status: string | null;
  message: string; details: Record<string, unknown>; created_at: string;
}
export interface QueueSummary {
  depth: number; failed: number; running: number; by_status: Record<string, number>;
}
export interface WorkerInstance {
  id: string; worker_identifier: string; status: string; last_heartbeat_at: string;
  current_job_id: string | null;
}
export interface WorkerPage { items: WorkerInstance[]; meta: PageMeta; }
export interface ImportSchedule {
  id: string; provider_id: string; name: string; symbols: string[]; mode: string;
  adjustment_preference: string; timezone: string; is_enabled: boolean;
  next_run_at: string; last_run_at: string | null; failure_count: number;
  last_error: string | null; date_range_policy: { lookback_days?: number };
}
export interface ReconciliationIssue {
  id: string; type: string; severity: string; record: string | null;
  outcome: string; resolution: string;
}
export interface ReconciliationReport {
  id?: string; status?: string; dry_run: boolean; records_checked: number;
  issue_count: number; conflict_count?: number; started_at?: string;
  issues?: ReconciliationIssue[] | Array<{ type: string; severity: string; record: string }>;
}
