import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api";
import { Layout } from "../components/Layout";
import { AssetDetail } from "../pages/AssetDetail";
import { AssetExplorer } from "../pages/AssetExplorer";
import { Overview } from "../pages/Overview";
import { Watchlists } from "../pages/Watchlists";
import { asset, bar, systemInfo, watchlist } from "./fixtures";
import { renderPage } from "./render";

vi.mock("../api", () => ({ api: {
  health: vi.fn(), systemInfo: vi.fn(), dataSources: vi.fn(), assets: vi.fn(), asset: vi.fn(),
  prices: vi.fn(), watchlists: vi.fn(), createWatchlist: vi.fn(), renameWatchlist: vi.fn(),
  deleteWatchlist: vi.fn(), addAsset: vi.fn(), removeAsset: vi.fn(),
}}));

vi.mock("../auth", () => ({
  useAuth: () => ({
    workspace: { id: "legacy", name: "Research workspace", role: "owner" },
    workspaces: [{ id: "legacy", name: "Research workspace", role: "owner" }],
    switchWorkspace: vi.fn(),
    signOut: vi.fn(),
  }),
}));

const mocked = vi.mocked(api);

beforeEach(() => {
  vi.clearAllMocks();
  mocked.health.mockResolvedValue({ status: "healthy", database: "healthy", version: "0.10.0" });
  mocked.systemInfo.mockResolvedValue(systemInfo);
  mocked.dataSources.mockResolvedValue([]);
  mocked.watchlists.mockResolvedValue([]);
  mocked.assets.mockResolvedValue({ items: [], pagination: { page: 1, page_size: 10, total: 0, pages: 0 } });
  mocked.asset.mockResolvedValue(asset);
  mocked.prices.mockResolvedValue({ symbol: "AAPL", items: [bar], pagination: { page: 1, page_size: 120, total: 1, pages: 1 } });
});

describe("application states", () => {
  it("renders the application navigation and warning", () => {
    renderPage(<Layout />);
    expect(screen.getByText("Market Intelligence")).toBeInTheDocument();
    expect(screen.getByText("Synthetic demonstration data — not live market data.")).toBeInTheDocument();
  });

  it("shows a loading state", () => {
    mocked.systemInfo.mockReturnValue(new Promise(() => {}));
    renderPage(<Overview />);
    expect(screen.getByRole("status")).toHaveTextContent("Loading market overview");
  });

  it("shows an API error state", async () => {
    mocked.systemInfo.mockRejectedValue(new Error("API offline"));
    renderPage(<Overview />);
    expect(await screen.findByRole("alert")).toHaveTextContent("API offline");
  });

  it("shows an empty asset state", async () => {
    renderPage(<AssetExplorer />);
    expect(await screen.findByText("No matching assets")).toBeInTheDocument();
  });
});

describe("watchlist workflow", () => {
  it("submits the watchlist creation form", async () => {
    mocked.createWatchlist.mockResolvedValue(watchlist);
    renderPage(<Watchlists />);
    await screen.findByText("No watchlists yet");
    await userEvent.type(screen.getByLabelText("New watchlist name"), "Core");
    await userEvent.click(screen.getByRole("button", { name: "Create watchlist" }));
    await waitFor(() => expect(mocked.createWatchlist.mock.calls[0]?.[0]).toBe("Core"));
  });

  it("adds an asset to a watchlist", async () => {
    mocked.watchlists.mockResolvedValue([watchlist]);
    mocked.addAsset.mockResolvedValue({ ...watchlist, assets: [{ symbol: "AAPL", name: "Apple Inc.", added_at: bar.event_time, latest_price: bar.close, latest_price_time: bar.event_time, is_demonstration_data: true }] });
    renderPage(<Watchlists />);
    const input = await screen.findByLabelText("Add asset to Core");
    await userEvent.type(input, "aapl");
    await userEvent.click(screen.getByRole("button", { name: "Add" }));
    await waitFor(() => expect(mocked.addAsset).toHaveBeenCalledWith("watch-1", "AAPL"));
  });
});

it("renders asset detail, price, chart labels, and provenance", async () => {
  renderPage(<AssetDetail />, "/assets/AAPL");
  expect(await screen.findByRole("heading", { name: "AAPL" })).toBeInTheDocument();
  expect(screen.getByText("$201.25")).toBeInTheDocument();
  expect(screen.getAllByText("Deterministic Synthetic Demonstration Provider")).toHaveLength(2);
  expect(screen.getByText("Synthetic demonstration")).toBeInTheDocument();
});
