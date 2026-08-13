import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api";
import { AuditLog } from "../pages/AuditLog";
import { BacktestManifest } from "../pages/BacktestManifest";
import { BacktestValidation } from "../pages/BacktestValidation";
import { InfrastructureServices } from "../pages/InfrastructureServices";
import { ProviderComparisons } from "../pages/ProviderComparisons";
import { SignIn } from "../pages/SignIn";
import { WorkspaceSettings } from "../pages/WorkspaceSettings";
import { renderPage } from "./render";

const state = vi.hoisted(() => ({
  loading: false,
  user: null as null | { id: string; email: string; email_verified: boolean; display_name: string; provider: string },
  workspace: { id: "workspace-a", name: "Workspace A", slug: "workspace-a", role: "viewer", created_at: "", updated_at: "" },
  workspaces: [] as Array<Record<string, string>>,
  sessionExpired: false,
  signIn: vi.fn(), signOut: vi.fn(), requestReset: vi.fn(), completeReset: vi.fn(), switchWorkspace: vi.fn(),
}));

vi.mock("../auth", () => ({
  AuthFlowError: class AuthFlowError extends Error {
    constructor(public code: string) { super(code); }
  },
  useAuth: () => state,
}));
vi.mock("../api", () => ({ api: {
  workspaceMembers: vi.fn(), inviteMember: vi.fn(), auditEvents: vi.fn(),
  infrastructureServices: vi.fn(), providerComparisons: vi.fn(),
  backtestManifest: vi.fn(), backtestValidation: vi.fn(),
} }));

const mocked = vi.mocked(api);

beforeEach(() => {
  vi.clearAllMocks(); state.user = null; state.sessionExpired = false; state.workspace.role = "viewer";
  mocked.workspaceMembers.mockResolvedValue([{ id: "member-a", email: "viewer@example.test", role: "viewer" }]);
  mocked.auditEvents.mockResolvedValue({ items: [{ id: "audit-a", timestamp: "2026-07-30T00:00:00Z", actor_user_id: "user-a", workspace_id: "workspace-a", action: "backtest.completed", resource_type: "backtest", resource_id: "run-a", result: "success", metadata: {}, correlation_id: "corr-a" }], page: 1, page_size: 50, total: 1 });
  mocked.infrastructureServices.mockResolvedValue({ contains_secrets: false, total: 1, items: [{ service_name: "Supabase", purpose: "Authentication", status: "evaluating", verification_date: "2026-07-30", free_tier_summary: "Bounded free plan", free_tier_limits: "Limits can change", production_criticality: "high", replacement_options: "OIDC provider", failure_effect: "New sign-ins unavailable", vendor_lock_in_risk: "medium" }] });
  mocked.providerComparisons.mockResolvedValue({ items: [{ id: "comparison-a", primary_provider_id: "one", secondary_provider_id: "two", summary: { conflicts: 1 }, disagreements: [{ type: "close_conflict" }], resolution_status: "conflict", resolution_reason: null, compared_at: "2026-07-30T00:00:00Z" }], total: 1 });
  mocked.backtestManifest.mockResolvedValue({ backtest_run_id: "run-a", status: "available", checksum: "abc", manifest: { application_version: "0.5.1", git_commit_sha: "deadbeef" } });
  mocked.backtestValidation.mockResolvedValue({ backtest_run_id: "run-a", overall_status: "failed", is_validated: false, rules: [{ name: "publication_time_leakage", status: "failed", critical: true, message: "Publication timestamps checked." }] });
});

describe("Sprint 5 secure multi-user workflows", () => {
  it("shows an invalid login state without echoing credentials", async () => {
    state.signIn.mockRejectedValueOnce(new Error("invalid"));
    renderPage(<SignIn />);
    expect(screen.getByRole("img", { name: "Market Intelligence Lab" })).toHaveAttribute(
      "src", "/assets/branding/market-intelligence-lab-logo-512.webp"
    );
    await userEvent.type(screen.getByLabelText("Email"), "user@example.test");
    await userEvent.type(screen.getByLabelText("Password"), "never-display-this");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Sign-in could not be completed");
    expect(screen.queryByText("never-display-this")).not.toBeInTheDocument();
  });

  it("disables repeated submission and exposes password-manager fields", async () => {
    state.signIn.mockReturnValueOnce(new Promise(() => {}));
    renderPage(<SignIn />);
    expect(screen.getByLabelText("Email")).toHaveAttribute("autocomplete", "email");
    expect(screen.getByLabelText("Password")).toHaveAttribute("autocomplete", "current-password");
    await userEvent.type(screen.getByLabelText("Email"), "owner@example.test");
    await userEvent.type(screen.getByLabelText("Password"), "not-a-real-password");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(screen.getByRole("button", { name: "Signing in…" })).toBeDisabled();
  });

  it("shows session expiry explicitly", () => {
    state.sessionExpired = true;
    renderPage(<SignIn />);
    expect(screen.getByRole("alert")).toHaveTextContent("session expired");
  });

  it("hides member management from viewers", async () => {
    renderPage(<WorkspaceSettings />);
    expect(await screen.findByText("viewer@example.test — viewer")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Invite member" })).not.toBeInTheDocument();
    expect(screen.getByText(/requires administrator permission/)).toBeInTheDocument();
  });

  it("renders immutable audit events", async () => {
    renderPage(<AuditLog />);
    expect(await screen.findByText("backtest.completed")).toBeInTheDocument();
    expect(screen.getByText("success")).toBeInTheDocument();
  });

  it("renders safe infrastructure governance metadata", async () => {
    renderPage(<InfrastructureServices />);
    expect(await screen.findByText("Supabase")).toBeInTheDocument();
    expect(screen.getByText(/Limits can change/)).toBeInTheDocument();
    expect(screen.getByText(/OIDC provider/)).toBeInTheDocument();
  });

  it("shows provider conflicts without silently selecting a value", async () => {
    renderPage(<ProviderComparisons />);
    expect(await screen.findByRole("heading", { name: "conflict" })).toBeInTheDocument();
    expect(screen.getByText(/never silently replaced/)).toBeInTheDocument();
  });

  it("renders reproducibility and critical validation results", async () => {
    renderPage(<><BacktestManifest /><BacktestValidation /></>, "/backtests/run-a/manifest", "/backtests/:id/manifest");
    expect(await screen.findByText(/"application_version": "0.5.1"/)).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText(/Overall:/)).toHaveTextContent("failed"));
    expect(screen.getByRole("heading", { name: /publication_time_leakage: failed/ })).toBeInTheDocument();
  });
});
