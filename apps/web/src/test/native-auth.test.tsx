import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { AuthProvider, ProtectedRoute, useAuth } from "../auth";
import { api, configureRequestContext } from "../api";
import { MemoryRouter, Route, Routes } from "react-router";
import { PasswordReset } from "../pages/PasswordReset";

vi.mock("../api", () => ({ api: {
  login: vi.fn(), logout: vi.fn(), changePassword: vi.fn(),
  currentUser: vi.fn(), workspaces: vi.fn(),
}, configureRequestContext: vi.fn() }));
const mocked = vi.mocked(api);
const token = "disposable-memory-only-session";
function Probe() {
  const auth = useAuth();
  return <div>
    <span>{auth.user ? "Authenticated" : "Signed out"}</span>
    {auth.sessionExpired && <span>Expired</span>}
    <span>{auth.workspace?.name}</span>
    <button onClick={() => void auth.signIn("owner", "disposable-password")}>Login</button>
    <button onClick={() => void auth.signOut()}>Logout</button>
    <button onClick={() => auth.switchWorkspace("two")}>Workspace</button>
    <button onClick={() => void auth.changePassword("current-password", "new-password")}>Password</button>
  </div>;
}
beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear(); sessionStorage.clear();
  mocked.login.mockResolvedValue({ access_token: token, token_type: "bearer" });
  mocked.logout.mockResolvedValue(undefined);
  mocked.changePassword.mockResolvedValue(undefined);
  mocked.currentUser.mockResolvedValue({ id: "user", email: "", display_name: "Owner", email_verified: false, provider: "native" });
  mocked.workspaces.mockResolvedValue([
    { id: "one", name: "First", slug: "first", role: "owner", created_at: "", updated_at: "" },
    { id: "two", name: "Second", slug: "second", role: "viewer", created_at: "", updated_at: "" },
  ]);
});
it("requires login, hydrates identity and preserves workspace choice without persisting credentials", async () => {
  render(<AuthProvider><Probe /></AuthProvider>);
  expect(screen.getByText("Signed out")).toBeInTheDocument();
  expect(mocked.currentUser).not.toHaveBeenCalled();
  fireEvent.click(screen.getByText("Login"));
  await screen.findByText("Authenticated");
  expect(configureRequestContext).toHaveBeenLastCalledWith(token, "one");
  fireEvent.click(screen.getByText("Workspace"));
  expect(configureRequestContext).toHaveBeenLastCalledWith(token, "two");
  expect(localStorage.getItem("mil:active-workspace")).toBe("two");
  expect(JSON.stringify(localStorage)).not.toContain(token);
  expect(sessionStorage.length).toBe(0);
  expect(document.cookie).not.toContain(token);
});
it("revokes before clearing and requires sign-in after remount", async () => {
  const view = render(<AuthProvider><Probe /></AuthProvider>);
  fireEvent.click(screen.getByText("Login"));
  await screen.findByText("Authenticated");
  fireEvent.click(screen.getByText("Logout"));
  await screen.findByText("Signed out");
  expect(mocked.logout).toHaveBeenCalledOnce();
  expect(configureRequestContext).toHaveBeenLastCalledWith(null, null);
  fireEvent.click(screen.getByText("Login"));
  await screen.findByText("Authenticated");
  view.unmount();
  render(<AuthProvider><Probe /></AuthProvider>);
  expect(screen.getByText("Signed out")).toBeInTheDocument();
  expect(mocked.login).toHaveBeenCalledTimes(2);
});
it("clears all auth state on expiry", async () => {
  render(<AuthProvider><Probe /></AuthProvider>);
  fireEvent.click(screen.getByText("Login"));
  await screen.findByText("Authenticated");
  act(() => window.dispatchEvent(new Event("mil:session-expired")));
  expect(screen.getByText("Signed out")).toBeInTheDocument();
  expect(screen.getByText("Expired")).toBeInTheDocument();
  expect(configureRequestContext).toHaveBeenLastCalledWith(null, null);
});
it("clears the session after password change", async () => {
  render(<AuthProvider><Probe /></AuthProvider>);
  fireEvent.click(screen.getByText("Login"));
  await screen.findByText("Authenticated");
  fireEvent.click(screen.getByText("Password"));
  await waitFor(() => expect(screen.getByText("Signed out")).toBeInTheDocument());
  expect(mocked.changePassword).toHaveBeenCalledOnce();
});

it("does not restore a token when a pending login completes after unmount", async () => {
  let complete!: (value: { access_token: string; token_type: string }) => void;
  mocked.login.mockReturnValueOnce(new Promise(resolve => { complete = resolve; }));
  const view = render(<AuthProvider><Probe /></AuthProvider>);
  fireEvent.click(screen.getByText("Login"));
  view.unmount();
  render(<AuthProvider><Probe /></AuthProvider>);
  await act(async () => complete({ access_token: token, token_type: "bearer" }));
  expect(configureRequestContext).toHaveBeenLastCalledWith(null, null);
  expect(mocked.currentUser).not.toHaveBeenCalled();
});

it("protects routes until login", async () => {
  render(<AuthProvider><MemoryRouter initialEntries={["/private"]}><Routes>
    <Route element={<ProtectedRoute />}><Route path="/private" element={<p>Private content</p>} /></Route>
    <Route path="/sign-in" element={<p>Sign-in required</p>} />
  </Routes></MemoryRouter></AuthProvider>);
  expect(await screen.findByText("Sign-in required")).toBeInTheDocument();
  expect(screen.queryByText("Private content")).not.toBeInTheDocument();
});

it("offers operator recovery while signed out and revokes after current-password confirmation", async () => {
  render(<AuthProvider><MemoryRouter><Probe /><PasswordReset /></MemoryRouter></AuthProvider>);
  expect(screen.getByText(/Contact the MIL operator/)).toBeInTheDocument();
  expect(screen.queryByLabelText("Current password")).not.toBeInTheDocument();
  fireEvent.click(screen.getByText("Login"));
  await screen.findByText("Authenticated");
  fireEvent.change(screen.getByLabelText("Current password"), { target: { value: "current-fixture" } });
  fireEvent.change(screen.getByLabelText("New password"), { target: { value: "long-new-fixture-password" } });
  fireEvent.click(screen.getByText("Change password"));
  await screen.findByText(/Password changed. Sign in again/);
  expect(mocked.changePassword).toHaveBeenCalledWith("current-fixture", "long-new-fixture-password");
  expect(screen.getByText("Signed out")).toBeInTheDocument();
});
