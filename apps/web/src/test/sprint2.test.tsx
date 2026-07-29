import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api";
import { BacktestDetail } from "../pages/BacktestDetail";
import { PaperPortfolioDetail } from "../pages/PaperPortfolioDetail";
import { PaperPortfolios } from "../pages/PaperPortfolios";
import { RiskSettings } from "../pages/RiskSettings";
import { SimulatedOrderTicket } from "../pages/SimulatedOrderTicket";
import { StrategyLab } from "../pages/StrategyLab";
import type { PaperPortfolio, Strategy } from "../types";
import { renderPage } from "./render";

vi.mock("../api", () => ({ api: {
  strategies: vi.fn(), createBacktest: vi.fn(), backtests: vi.fn(), backtest: vi.fn(),
  backtestTrades: vi.fn(), backtestEquity: vi.fn(), paperPortfolios: vi.fn(),
  createPaperPortfolio: vi.fn(), paperPortfolio: vi.fn(), paperOrders: vi.fn(),
  paperFills: vi.fn(), paperPerformance: vi.fn(), previewOrder: vi.fn(), submitOrder: vi.fn(), cancelOrder: vi.fn(),
  pausePortfolio: vi.fn(), resumePortfolio: vi.fn(), riskRules: vi.fn(), updateRiskRule: vi.fn(),
} }));

const mocked = vi.mocked(api);
const strategy: Strategy = {
  id: "strategy-1", name: "Buy and Hold", strategy_type: "buy_and_hold",
  description: "Invest once and remain invested.", is_builtin: true,
  latest_version: { id: "version-1", version: 1, parameters: {}, parameter_schema: {}, calculation_notes: "One deterministic entry.", created_at: "2026-01-01T00:00:00Z" }, versions: [],
};
const portfolio: PaperPortfolio = {
  id: "portfolio-1", name: "Research", currency: "USD", starting_cash: "100000",
  cash_balance: "100000", portfolio_value: "100000", realized_pnl: "0", unrealized_pnl: "0",
  exposure: "0", status: "active", positions: [], open_order_count: 0,
  created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z",
  warning: "Hypothetical simulated portfolio — no real orders.",
};

beforeEach(() => {
  vi.clearAllMocks();
  mocked.strategies.mockResolvedValue({ items: [strategy], page: 1, page_size: 100, total: 1 });
  mocked.paperPortfolios.mockResolvedValue([]);
  mocked.createPaperPortfolio.mockResolvedValue(portfolio);
  mocked.riskRules.mockResolvedValue([{ id: "rule-1", rule_type: "maximum_order_value", limit_value: "50000", is_enabled: true, configuration: {} }]);
  mocked.paperPortfolio.mockResolvedValue(portfolio);
  mocked.paperOrders.mockResolvedValue([]);
  mocked.paperFills.mockResolvedValue([]);
  mocked.paperPerformance.mockResolvedValue({ portfolio_id: "portfolio-1", starting_cash: "100000", current_value: "100000", total_return: "0", realized_pnl: "0", unrealized_pnl: "0", points: [{ event_time: "2026-01-01T00:00:00Z", equity: "100000", cash: "100000" }], warning: "Hypothetical" });
});

describe("Sprint 2 research workflows", () => {
  it("submits a transparent backtest configuration", async () => {
    mocked.createBacktest.mockResolvedValue({
      id: "run-1", strategy_version_id: "version-1", strategy_name: "Buy and Hold",
      strategy_type: "buy_and_hold", status: "completed", asset_symbols: ["AAPL", "MSFT"],
      benchmark_symbol: "SPY", start_time: "2025-01-02T21:00:00Z", end_time: "2025-06-18T21:00:00Z",
      initial_cash: "100000", final_equity: "105000", cash_balance: "0", metrics: {},
      strategy_configuration: {}, risk_configuration: {}, execution_assumptions: {},
      data_source_identifiers: [], application_version: "0.2.0", is_hypothetical: true,
      created_at: "2026-01-01T00:00:00Z",
    });
    renderPage(<StrategyLab />, "/strategies");
    expect(await screen.findByText("Buy and Hold")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Run backtest" }));
    await waitFor(() => expect(mocked.createBacktest).toHaveBeenCalled());
    expect(mocked.createBacktest.mock.calls[0]?.[0]).toMatchObject({ symbols: ["AAPL", "MSFT"], execution_delay: 1 });
  });

  it("validates strategy parameters before submission", async () => {
    renderPage(<StrategyLab />, "/strategies");
    const input = await screen.findByLabelText("Strategy parameters");
    await userEvent.clear(input); await userEvent.type(input, "not-json");
    await userEvent.click(screen.getByRole("button", { name: "Run backtest" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("valid JSON object");
    expect(mocked.createBacktest).not.toHaveBeenCalled();
  });

  it("displays backtest metrics, benchmark, drawdown, and provenance", async () => {
    mocked.backtest.mockResolvedValue({ id: "run-1", strategy_version_id: "version-1", strategy_name: "Buy and Hold", strategy_type: "buy_and_hold", status: "completed", asset_symbols: ["AAPL"], benchmark_symbol: "SPY", start_time: "2025-01-02T21:00:00Z", end_time: "2025-06-18T21:00:00Z", initial_cash: "100000", final_equity: "105000", cash_balance: "1000", metrics: { total_return: 0.05, annualized_return: 0.1, maximum_drawdown: -0.02, sharpe_ratio: 1.2, benchmark_return: 0.03 }, strategy_configuration: {}, risk_configuration: {}, execution_assumptions: { execution_delay: 1 }, data_source_identifiers: ["source-1"], application_version: "0.2.0", is_hypothetical: true, created_at: "2026-01-01T00:00:00Z" });
    mocked.backtestTrades.mockResolvedValue([]);
    mocked.backtestEquity.mockResolvedValue([{ event_time: "2025-01-02T21:00:00Z", equity: "105000", benchmark_value: "103000", cash: "1000", exposure: "0.99", drawdown: "-0.02", cumulative_fees: "1" }]);
    renderPage(<BacktestDetail />, "/backtests/run-1", "/backtests/:id");
    expect(await screen.findByText("5.00%")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Benchmark curve" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Drawdown chart" })).toBeInTheDocument();
    expect(screen.getByText(/Hypothetical results · synthetic data/)).toBeInTheDocument();
  });

  it("creates a paper portfolio", async () => {
    renderPage(<PaperPortfolios />, "/paper-portfolios");
    await screen.findByText("No paper portfolios");
    await userEvent.type(screen.getByLabelText("Portfolio name"), "Research");
    await userEvent.click(screen.getByRole("button", { name: "Create portfolio" }));
    await waitFor(() => expect(mocked.createPaperPortfolio).toHaveBeenCalledWith("Research", "100000"));
  });

  it("previews risk checks before simulated submission", async () => {
    mocked.previewOrder.mockResolvedValue({ outcome: "would_fill", estimated_price: "201.25", estimated_value: "2012.50", estimated_fees: "1", rejection_reasons: [], source_price_bar_id: "bar-source-1", assumptions: { gap_rule: "marketable gaps use bar open" }, is_triggered: false });
    renderPage(<SimulatedOrderTicket />, "/paper-portfolios/portfolio-1/order", "/paper-portfolios/:id/order");
    await userEvent.click(screen.getByRole("button", { name: "Preview risk checks" }));
    expect(await screen.findByText("All enabled portfolio risk checks passed.")).toBeInTheDocument();
    expect(mocked.previewOrder).toHaveBeenCalled();
  });

  it("shows risk rejection details and validates conditional order fields", async () => {
    mocked.previewOrder.mockResolvedValue({ outcome: "rejected", estimated_price: "201.25", estimated_value: "100625", estimated_fees: "1", rejection_reasons: ["Order value exceeds maximum order value 50000.00."], source_price_bar_id: "bar-source-1", assumptions: { gap_rule: "marketable gaps use bar open" }, is_triggered: false });
    renderPage(<SimulatedOrderTicket />, "/paper-portfolios/portfolio-1/order", "/paper-portfolios/:id/order");
    await userEvent.click(screen.getByRole("button", { name: "Preview risk checks" }));
    expect(await screen.findByText(/exceeds maximum order value/)).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText("Order type"), "limit");
    await userEvent.click(screen.getByRole("button", { name: "Submit simulated order" }));
    expect(mocked.submitOrder).not.toHaveBeenCalled();
  });

  it("displays positions and pending orders", async () => {
    mocked.paperPortfolio.mockResolvedValue({ ...portfolio, positions: [{ id: "position-1", symbol: "AAPL", name: "Apple Inc.", sector: "Technology", quantity: "10", average_cost: "200", mark_price: "201", market_value: "2010", realized_pnl: "0", unrealized_pnl: "10" }], open_order_count: 1 });
    mocked.paperOrders.mockResolvedValue([{ id: "order-1", client_order_id: "client-1", symbol: "AAPL", side: "buy", order_type: "limit", quantity: "1", limit_price: "180", stop_price: null, status: "pending", is_triggered: false, rejection_reason: null, estimated_value: null, estimated_fees: "1", submitted_at: "2026-01-01T00:00:00Z", cancelled_at: null, idempotent_replay: false }]);
    renderPage(<PaperPortfolioDetail />, "/paper-portfolios/portfolio-1", "/paper-portfolios/:id");
    expect(await screen.findByText("Apple Inc.")).toBeInTheDocument();
    expect(screen.getByText("pending")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Portfolio value chart" })).toBeInTheDocument();
  });

  it("updates an explicit risk rule", async () => {
    mocked.updateRiskRule.mockResolvedValue({ id: "rule-1", rule_type: "maximum_order_value", limit_value: "25000", is_enabled: true, configuration: {} });
    renderPage(<RiskSettings />, "/paper-portfolios/portfolio-1/risk", "/paper-portfolios/:id/risk");
    const input = await screen.findByLabelText("maximum_order_value");
    await userEvent.clear(input); await userEvent.type(input, "25000");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(mocked.updateRiskRule).toHaveBeenCalledWith("portfolio-1", "rule-1", "25000", true));
  });
});
