import { QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router";
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
import { AuthProvider, ProtectedRoute } from "./auth";
import { queryClient } from "./queryClient";
import { SignIn } from "./pages/SignIn";
import { PasswordReset } from "./pages/PasswordReset";
import { UserProfile } from "./pages/UserProfile";
import { WorkspaceSettings } from "./pages/WorkspaceSettings";
import { AuditLog } from "./pages/AuditLog";
import { InfrastructureServices } from "./pages/InfrastructureServices";
import { ProviderComparisons } from "./pages/ProviderComparisons";
import { BacktestManifest } from "./pages/BacktestManifest";
import { BacktestValidation } from "./pages/BacktestValidation";
import { AnalyticsComparison } from "./pages/AnalyticsComparison";
import { OptionalEngineStatus } from "./pages/OptionalEngineStatus";
import { OptimizationExperiment } from "./pages/OptimizationExperiment";
import { SecFilingDetail } from "./pages/SecFilingDetail";
import { SecFilings } from "./pages/SecFilings";
import { SecInsiderTransactions } from "./pages/SecInsiderTransactions";
import { SecInstitutionalHoldings } from "./pages/SecInstitutionalHoldings";
import { UpstreamIntegrations } from "./pages/UpstreamIntegrations";
import { UpstreamLicenseInventory } from "./pages/UpstreamLicenseInventory";
import { WorldDataSources } from "./pages/WorldDataSources";
import { WorldDataSourceDetail } from "./pages/WorldDataSourceDetail";
import { DataManifests, DataManifestDetail } from "./pages/DataManifests";
import { MacroExplorer } from "./pages/MacroExplorer";
import { EnergyExplorer } from "./pages/EnergyExplorer";
import { CompanyDriverProfile } from "./pages/CompanyDriverProfile";
import { DataRelevance } from "./pages/DataRelevance";
import { EconomicGraphExplorer } from "./pages/EconomicGraphExplorer";
import { EntityResolutionReview } from "./pages/EntityResolutionReview";
import { RelationshipEvidence } from "./pages/RelationshipEvidence";

export { queryClient };

export function App() {
  return <QueryClientProvider client={queryClient}><BrowserRouter><AuthProvider><Routes>
    <Route path="sign-in" element={<SignIn />} />
    <Route path="reset-password" element={<PasswordReset />} />
    <Route element={<ProtectedRoute />}><Route element={<Layout />}>
      <Route index element={<Overview />} />
      <Route path="watchlists" element={<Watchlists />} />
      <Route path="assets" element={<AssetExplorer />} />
      <Route path="assets/:symbol" element={<AssetDetail />} />
      <Route path="strategies" element={<StrategyLab />} />
      <Route path="backtests" element={<Backtests />} />
      <Route path="backtests/:id" element={<BacktestDetail />} />
      <Route path="backtests/:id/manifest" element={<BacktestManifest />} />
      <Route path="backtests/:id/validation" element={<BacktestValidation />} />
      <Route path="paper-portfolios" element={<PaperPortfolios />} />
      <Route path="paper-portfolios/:id" element={<PaperPortfolioDetail />} />
      <Route path="paper-portfolios/:id/order" element={<SimulatedOrderTicket />} />
      <Route path="paper-portfolios/:id/risk" element={<RiskSettings />} />
      <Route path="data-sources" element={<DataSources />} />
      <Route path="world-data" element={<WorldDataSources />} />
      <Route path="world-data/sources/:id" element={<WorldDataSourceDetail />} />
      <Route path="world-data/manifests" element={<DataManifests />} />
      <Route path="world-data/manifests/:id" element={<DataManifestDetail />} />
      <Route path="world-data/macro" element={<MacroExplorer />} />
      <Route path="world-data/energy" element={<EnergyExplorer />} />
      <Route path="economic-graph" element={<EconomicGraphExplorer />} />
      <Route path="driver-profiles" element={<CompanyDriverProfile />} />
      <Route path="relationship-evidence" element={<RelationshipEvidence />} />
      <Route path="data-relevance" element={<DataRelevance />} />
      <Route path="entity-resolution" element={<EntityResolutionReview />} />
      <Route path="providers" element={<Providers />} />
      <Route path="providers/:id" element={<ProviderDetail />} />
      <Route path="imports" element={<ImportJobs />} />
      <Route path="imports/:id" element={<ImportJobDetail />} />
      <Route path="operations" element={<Operations />} />
      <Route path="schedules" element={<Schedules />} />
      <Route path="reconciliation" element={<Reconciliation />} />
      <Route path="provider-comparisons" element={<ProviderComparisons />} />
      <Route path="infrastructure" element={<InfrastructureServices />} />
      <Route path="sec" element={<SecFilings />} />
      <Route path="sec/filings/:id" element={<SecFilingDetail />} />
      <Route path="sec/insiders" element={<SecInsiderTransactions />} />
      <Route path="sec/holdings" element={<SecInstitutionalHoldings />} />
      <Route path="analytics" element={<AnalyticsComparison />} />
      <Route path="optimization" element={<OptimizationExperiment />} />
      <Route path="upstream" element={<UpstreamIntegrations />} />
      <Route path="upstream/licenses" element={<UpstreamLicenseInventory />} />
      <Route path="upstream/engines" element={<OptionalEngineStatus />} />
      <Route path="profile" element={<UserProfile />} />
      <Route path="workspace" element={<WorkspaceSettings />} />
      <Route path="audit" element={<AuditLog />} />
      <Route path="data-quality" element={<DataQuality />} />
      <Route path="corporate-actions" element={<CorporateActions />} />
      <Route path="exchange-calendar" element={<ExchangeCalendar />} />
      <Route path="status" element={<SystemStatus />} />
      <Route path="docs" element={<Documentation />} />
    </Route></Route>
  </Routes></AuthProvider></BrowserRouter></QueryClientProvider>;
}
