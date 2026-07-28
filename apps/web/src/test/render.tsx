import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

export function renderPage(element: ReactElement, route = "/", routePattern = "*") {
  window.history.pushState({}, "Test", route);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[route]}><Routes><Route path={routePattern} element={element} /></Routes></MemoryRouter></QueryClientProvider>);
}
