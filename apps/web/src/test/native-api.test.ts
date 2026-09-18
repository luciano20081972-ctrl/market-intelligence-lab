import { afterEach, expect, it, vi } from "vitest";
import { api, configureRequestContext } from "../api";

afterEach(() => { vi.unstubAllGlobals(); configureRequestContext(null, null); });

it("does not report session expiry for rejected login without a session", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("{}", { status: 401 })));
  const expired = vi.fn();
  window.addEventListener("mil:session-expired", expired);
  try {
    await expect(api.login("owner", "incorrect")).rejects.toThrow();
    expect(expired).not.toHaveBeenCalled();
  } finally { window.removeEventListener("mil:session-expired", expired); }
});

it("does not expire a new session for an old request's late 401", async () => {
  let complete!: (response: Response) => void;
  vi.stubGlobal("fetch", vi.fn().mockReturnValue(new Promise(resolve => { complete = resolve; })));
  const expired = vi.fn();
  window.addEventListener("mil:session-expired", expired);
  try {
    configureRequestContext("old-disposable-token", null);
    const pending = api.currentUser();
    configureRequestContext("new-disposable-token", null);
    complete(new Response("{}", { status: 401 }));
    await expect(pending).rejects.toThrow();
    expect(expired).not.toHaveBeenCalled();
  } finally { window.removeEventListener("mil:session-expired", expired); }
});

it("keeps bearer and workspace context on identity operations and never sends cookies", async () => {
  const observed: Array<{ path: string; init: RequestInit }> = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init: RequestInit) => {
    observed.push({ path: new URL(url).pathname, init });
    return new Response(JSON.stringify({ ok: true }), { status: 200 });
  }));
  configureRequestContext("disposable-bearer", "selected-workspace");
  await api.workspaces();
  await api.workspace("selected-workspace");
  await api.workspaceMembers("selected-workspace");
  await api.auditEvents("selected-workspace");
  await api.updateCurrentUser("Owner display name");
  await api.inviteMember("selected-workspace", "fixture@example.test", "viewer");
  expect(observed).toHaveLength(6);
  for (const { init } of observed) {
    const headers = new Headers(init.headers);
    expect(headers.get("Authorization")).toBe("Bearer disposable-bearer");
    expect(headers.get("X-Workspace-ID")).toBe("selected-workspace");
    expect(init.credentials).toBe("omit");
    expect(headers.has("Cookie")).toBe(false);
  }
  configureRequestContext(null, null);
  await api.authHealth();
  expect(new Headers(observed.at(-1)!.init.headers).has("Authorization")).toBe(false);
});

it("handles empty logout/password responses without parsing or persisting a credential", async () => {
  const fetcher = vi.fn().mockImplementation(async () => new Response(null, { status: 204 }));
  vi.stubGlobal("fetch", fetcher);
  configureRequestContext("disposable-bearer", null);
  await expect(api.changePassword("current-fixture", "next-fixture-password")).resolves.toBeUndefined();
  await expect(api.logout()).resolves.toBeUndefined();
  expect(fetcher.mock.calls.every(([, init]) => init.credentials === "omit")).toBe(true);
  expect(JSON.stringify(localStorage)).not.toContain("disposable-bearer");
  expect(JSON.stringify(sessionStorage)).not.toContain("disposable-bearer");
});
