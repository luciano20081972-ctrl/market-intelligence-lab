import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { AssetDetail } from "./pages/AssetDetail";
import { AssetExplorer } from "./pages/AssetExplorer";
import { BacktestDetail } from "./pages/BacktestDetail";
import { Backtests } from "./pages/Backtests";
import { CorporateActions } from "./pages/CorporateActions";
import { DataQuality } from "./pages/DataQuality";
import { DataSources } from "./pages/DataSources";
import { ExchangeCalendar } from "./pages/ExchangeCalendar";
import { ImportJobDetail } from "./pages/ImportJobDetail";
import { ImportJobs } from "./pages/ImportJobs";
import { Documentation } from "./pages/Documentation";
import { Overview } from "./pages/Overview";
import { Providers } from "./pages/Providers";
import { ProviderDetail } from "./pages/ProviderDetail";
import { Operations } from "./pages/Operations";
import { Reconciliation } from "./pages/Reconciliation";
import { Schedules } from "./pages/Schedules";
import { PaperPortfolioDetail } from "./pages/PaperPortfolioDetail";
import { PaperPortfolios } from "./pages/PaperPortfolios";
import { RiskSettings } from "./pages/RiskSettings";
import { SimulatedOrderTicket } from "./pages/SimulatedOrderTicket";
import { StrategyLab } from "./pages/StrategyLab";
import { SystemStatus } from "./pages/SystemStatus";
import { Watchlists } from "./pages/Watchlists";

export const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 30_000 } } });

export function App() {
  return <QueryClientProvider client={queryClient}><BrowserRouter><Routes>
    <Route element={<Layout />}>
      <Route index element={<Overview />} />
      <Route path="watchlists" element={<Watchlists />} />
      <Route path="assets" element={<AssetExplorer />} />
      <Route path="assets/:symbol" element={<AssetDetail />} />
      <Route path="strategies" element={<StrategyLab />} />
      <Route path="backtests" element={<Backtests />} />
      <Route path="backtests/:id" element={<BacktestDetail />} />
      <Route path="paper-portfolios" element={<PaperPortfolios />} />
      <Route path="paper-portfolios/:id" element={<PaperPortfolioDetail />} />
      <Route path="paper-portfolios/:id/order" element={<SimulatedOrderTicket />} />
      <Route path="paper-portfolios/:id/risk" element={<RiskSettings />} />
      <Route path="data-sources" element={<DataSources />} />
      <Route path="providers" element={<Providers />} />
      <Route path="providers/:id" element={<ProviderDetail />} />
      <Route path="imports" element={<ImportJobs />} />
      <Route path="imports/:id" element={<ImportJobDetail />} />
      <Route path="operations" element={<Operations />} />
      <Route path="schedules" element={<Schedules />} />
      <Route path="reconciliation" element={<Reconciliation />} />
      <Route path="data-quality" element={<DataQuality />} />
      <Route path="corporate-actions" element={<CorporateActions />} />
      <Route path="exchange-calendar" element={<ExchangeCalendar />} />
      <Route path="status" element={<SystemStatus />} />
      <Route path="docs" element={<Documentation />} />
    </Route>
  </Routes></BrowserRouter></QueryClientProvider>;
}
