import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { AssetDetail } from "./pages/AssetDetail";
import { AssetExplorer } from "./pages/AssetExplorer";
import { DataSources } from "./pages/DataSources";
import { Documentation } from "./pages/Documentation";
import { Overview } from "./pages/Overview";
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
      <Route path="data-sources" element={<DataSources />} />
      <Route path="status" element={<SystemStatus />} />
      <Route path="docs" element={<Documentation />} />
    </Route>
  </Routes></BrowserRouter></QueryClientProvider>;
}
