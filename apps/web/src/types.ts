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
  capability: string;
  freshness: string;
  feed: string;
  provider: string | null;
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
  daily_move_pct: string | null;
  freshness: string;
  source: string | null;
  feed: string;
  capability: string;
}

export interface MarketFoundation {
  catalog_securities: number; historical_assets: number; real_price_bars: number;
  realtime_active: number; operating_mode: string; automatic_refresh: string;
  real_market_status: string; message: string;
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

export interface CurrentUser { id: string; email: string; email_verified: boolean; display_name: string; provider: string }
export interface WorkspaceSummary { id: string; name: string; slug: string; role: "owner" | "admin" | "member" | "viewer"; created_at: string; updated_at: string }
export interface AuditEvent { id: string; timestamp: string; actor_user_id: string | null; workspace_id: string; action: string; resource_type: string; resource_id: string; result: string; metadata: Record<string, unknown>; correlation_id: string | null }
export interface AuditPage { items: AuditEvent[]; page: number; page_size: number; total: number }
export interface InfrastructureService { service_name: string; purpose: string; status: string; verification_date: string; free_tier_summary: string; free_tier_limits: string; production_criticality: string; replacement_options: string; failure_effect: string; vendor_lock_in_risk: string }
export interface InfrastructureRegistry { items: InfrastructureService[]; total: number; contains_secrets: boolean }
export interface ProviderComparison { id: string; primary_provider_id: string; secondary_provider_id: string; summary: Record<string, unknown>; disagreements: Array<Record<string, unknown>>; resolution_status: string; resolution_reason: string | null; compared_at: string }
export interface BacktestManifest { backtest_run_id: string; status: string; checksum?: string; manifest: Record<string, unknown> }
export interface BacktestValidation { backtest_run_id: string; overall_status: string; is_validated: boolean; rules: Array<{ name: string; status: string; critical: boolean; message: string }> }

export interface SecCompany {
  id: string; cik: string; name: string; tickers: string[]; sic: string | null;
  submissions_url: string; facts_url: string; retrieved_at: string; source_checksum: string;
}
export interface SecFiling {
  id: string; company_id: string; company_name: string | null; cik: string | null;
  accession_number: string; form_type: string; filing_date: string; accepted_at: string;
  reporting_period: string | null; source_url: string; retrieved_at: string;
  content_checksum: string; raw_document_reference: string; parser_version: string;
  edgartools_version: string; is_amendment: boolean; simulation_eligible_at: string;
  documents?: Array<Record<string, unknown>>; facts?: Array<Record<string, unknown>>;
}
export interface SecInsiderTransaction {
  id: string; company_id: string; filing_id: string; owner_name: string; relationship: string;
  transaction_code: string; security_title: string; transaction_date: string; shares: string;
  price: string | null; acquired_disposed: string;
}
export interface SecInstitutionalHolding {
  id: string; filing_id: string; company_id: string | null; issuer_name: string; cusip: string;
  as_of_date: string; shares: string; value_usd: string; voting_authority: Record<string, number>;
}
export interface UpstreamProject {
  name: string; repository_url: string; reviewed_revision: string; reviewed_release: string;
  license: string; integration_category: string; approved_use: string; prohibited_use: string;
  dependency_version: string | null; maintenance_status: string; security_status: string;
  commercial_use_status: string;
}
export interface UpstreamHealth {
  status: string; available: boolean; message: string;
  version: { project: string; adapter_version: string; library_version: string | null; source_commit: string | null };
  capabilities: Array<{ code: string; description: string; fixture_tested: boolean; live_verified: boolean }>;
}
export interface AnalyticsComparisonResult {
  id: string; canonical_metrics: Record<string, number | null>;
  quantstats_metrics: Record<string, number | null>;
  reconciliation: Array<{ metric: string; absolute_difference: number | null; agreement_status: string; methodology_note: string }>;
  agreement_status: string; engine_versions: Record<string, string>; return_series_checksum: string;
}
export interface OptimizationResult {
  id: string; model: string; asset_universe: string[]; weights: Record<string, number>;
  objective_values: Record<string, number>; risk_metrics: Record<string, number>;
  constraints: Record<string, unknown>; optimizer_version: string; warnings: string[];
}

export interface WorldDataSource {
  id: string; provider: string; title: string; transport: string; official_url: string;
  expected_frequency: string; license: string; temporal_mode: string; configured: boolean;
}
export interface DataManifestRecord {
  id: string; source_id: string; dataset_id: string; retrieval_time: string;
  raw_object_reference: string; checksum: string; record_count: number;
  accepted_count: number; rejected_count: number; quality_summary: Record<string, number>;
}
export interface WorldSeries {
  id: string; source_id: string; external_id: string; title: string; units: string;
  frequency: string; geography?: string;
}
export interface WorldObservation {
  id: string; source_value: string; numeric_value: string | null; observation_time: string;
  revision_time: string; simulation_eligible_time: string; quality_flags: string[];
}

export interface EconomicEntity {
  id: string; entity_type: string; canonical_name: string; status: string;
  valid_from: string; valid_to: string | null; first_seen: string; last_verified: string;
  simulation_eligible_time: string; confidence: string; provenance: Record<string, unknown>;
}
export interface EconomicEntityPage {
  items: EconomicEntity[]; page: number; page_size: number; total: number;
}
export interface GraphRelationship {
  id: string; subject_entity_id: string; predicate: string; object_entity_id: string;
  confidence: string; status: string; valid_from: string; valid_to: string | null;
  simulation_eligible_time: string;
}
export interface GraphPathExplanation {
  entity_ids: string[]; relationship_ids: string[]; depth: number;
  explanation: Array<Record<string, unknown>>;
}
export interface EconomicGraph {
  as_of: string; max_depth: number; max_nodes: number; nodes: EconomicEntity[];
  relationships: GraphRelationship[]; paths: GraphPathExplanation[];
  path_explanations: GraphPathExplanation[]; truncated: boolean;
}
export interface DriverEntry {
  id: string; driver_category: string; linked_entity_ids: string[];
  supporting_relationship_ids: string[]; prior_relevance: string;
  evidence_relevance: string; historical_evidence_relevance: string | null;
  user_override: string | null; effective_relevance: string; confidence: string;
  explanation: string;
}
export interface CompanyDriverProfile {
  id: string; company_entity_id: string; prior_version: string; version: number;
  generated_at: string; simulation_eligible_time: string; trigger_reason: string;
  scientific_label: string; entries: DriverEntry[];
}
export interface RelationshipEvidence {
  id: string; relationship_id: string; direction: string;
  source_record_identifier: string; evidence_type: string; publication_time: string;
  simulation_eligible_time: string; confidence: string; content_reference: string;
  supporting_text: string | null;
}
export interface RelevanceDecision {
  id: string; dataset_id: string; decision: "PROCESS" | "DEFER" | "IGNORE" | "REVIEW";
  relevance_score: string; reason_codes: string[];
  supporting_graph_paths: Array<Record<string, unknown>>; confidence: string; created_at: string;
}
export interface DataRelevancePage {
  company_entity_id: string; profile_id: string; router_version: string | null;
  items: RelevanceDecision[]; total: number;
}
export interface ResolutionCandidate {
  id: string; namespace: string; value: string; normalized_value: string;
  candidate_entity_id: string; method: string; confidence: string; source: string;
  evidence: Record<string, unknown>; resolver_version: string; status: string;
  resolved_at: string;
}

export interface ResearchFeature {
  id: string;
  feature_key: string;
  name: string;
  description: string;
  domain: string;
  entity_type: string;
  status: string;
}

export interface ResearchUniverse {
  id: string;
  name: string;
  description: string;
  source: string;
  owner_type: string;
  selection_rules: Record<string, unknown>;
}

export interface FeatureValueRecord {
  id: string;
  feature_key: string;
  entity_id: string;
  observation_time: string;
  simulation_eligible_time: string;
  value: string | null;
  unit: string;
  quality_state: string;
  input_checksum: string;
  computation_checksum: string;
}

export interface ResearchDecision {
  id: string;
  entity_id: string;
  score: string;
  score_components: Record<string, string>;
  recommendation: string;
  reason_codes: string[];
  missing_information: string[];
  level: string;
}

export interface ScreeningRun {
  id: string;
  as_of_time: string;
  total_candidates: number;
  promoted: number;
  deferred: number;
  demoted: number;
  rejected: number;
  budget_usage: Record<string, unknown>;
  reason_distribution: Record<string, number>;
  checksum: string;
  funnel: Record<string, number>;
  decisions: ResearchDecision[];
}

export interface ResearchCandidate {
  id: string;
  entity_id: string;
  company_name: string;
  archetype: string;
  current_level: string;
  previous_level: string | null;
  promotion_reason: string | null;
  demotion_reason: string | null;
  budget_impact: Record<string, unknown>;
  next_review_time: string;
  selected_pipelines?: string[];
  irrelevant_pipelines_skipped?: boolean;
}

export interface ResearchBudget {
  id: string;
  level: string;
  limits: Record<string, number>;
  cost_class: string;
  monetary_estimate: string | null;
}

export interface ResearchHypothesis {
  id: string;
  subject_entity_id: string;
  company_name: string;
  title: string;
  type: string;
  economic_rationale: string;
  mechanism: Record<string, unknown>;
  expected_direction: string;
  expected_horizon: string;
  required_evidence: Array<Record<string, unknown>>;
  required_graph_drivers: string[];
  required_datasets: string[];
  proposed_outcome: Record<string, unknown>;
  candidate_feature_specification: Record<string, unknown>;
  originating_method: string;
  falsification_criteria: string[];
  mechanism_confidence: string;
  novelty_estimate: string;
  assumptions: string[];
  simulation_eligible_time: string;
  status: string;
  version: number;
  semantics: string;
  mechanisms?: Array<Record<string, unknown>>;
  evidence?: Array<Record<string, unknown>>;
  feature_specs?: Array<Record<string, unknown>>;
}

export interface FactorExperiment {
  id: string;
  hypothesis_id: string;
  candidate_feature_spec_id: string;
  universe_version_id: string;
  feature_snapshot_id: string;
  outcome_definition_id: string;
  status: string;
  conclusion: string | null;
  period_start: string;
  period_end: string;
  validation_protocol: Record<string, unknown>;
  cost_assumptions: Record<string, unknown>;
  dependency_versions: Record<string, string>;
  seed: number;
  warnings: string[];
  immutable: boolean;
}

export interface ExperimentFold {
  id: string;
  fold_number: number;
  train: [string, string];
  validation: [string, string];
  final_out_of_sample_test: [string, string];
  purge_observations: number;
  embargo_observations: number;
  observations: number;
  coverage: string;
  factor_statistics: Record<string, number | string | string[]>;
  model_statistics: Record<string, number | string | boolean>;
  warnings: string[];
  failures: string[];
}

export interface PromotionEvent {
  from_stage: string | null;
  to_stage: string;
  decision: string;
  reasons: string[];
  gate_version: string;
}

export interface ResearchEngineStatus {
  engine: string;
  version: string | null;
  available: boolean;
  enabled: boolean;
  message: string;
  capabilities: string[];
  security_boundaries: string[];
}

export interface ResearchMemory {
  id: string;
  hypothesis_id: string;
  experiment_id: string;
  subject_entity_id: string;
  company_name: string | null;
  feature_key: string;
  outcome_key: string;
  conclusion: "POSITIVE" | "NEGATIVE";
  status: "ACTIVE" | "WEAK" | "CONTRADICTED" | "SUPERSEDED" | "RETIRED";
  datasets: string[];
  feature_domains: string[];
  applicability: Record<string, unknown>;
  regime_context: string[];
  period_context: Record<string, unknown>;
  result_summary: Record<string, unknown>;
  failure_reasons: string[];
  success_conditions: string[];
  failure_conditions: string[];
  confidence: string;
  first_learned_at: string;
  last_confirmed_at: string;
  simulation_eligible_time: string;
  memory_decisions?: Array<{
    classification: string;
    decision: string;
    reason: string;
    override_authorized: boolean;
    policy_version: string;
  }>;
  graph_path?: Array<Record<string, unknown>>;
  provenance?: Record<string, unknown>;
}

export interface SignalIndependence {
  id: string;
  experiment_id: string;
  factor_key: string;
  baseline_version: string;
  methodology_version: string;
  predictive_strength: string;
  independent_contribution: string;
  redundancy_score: string;
  independent_information_score: string;
  components: Record<string, number | string | Record<string, number>>;
  formula: Record<string, unknown>;
  segments: Record<string, unknown>;
  as_of_time: string;
  semantics: string;
}

export interface DivergenceEventRecord {
  id: string;
  definition_id: string;
  subject_entity_id: string;
  company_name: string | null;
  as_of_time: string;
  domain_values: Record<string, { raw: number; normalized: number }>;
  magnitude_components: Record<string, number | boolean | string>;
  disagreement_magnitude: string;
  persistence_periods: number;
  data_completeness: string;
  evidence: Record<string, unknown>;
  historical_analogues: Array<Record<string, unknown>>;
  confidence: string;
  research_priority: string;
  status: string;
  research_candidate_id: string | null;
  paper_eligible: false;
  semantics: string;
}
