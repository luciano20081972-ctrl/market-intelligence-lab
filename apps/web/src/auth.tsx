import { createContext, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Navigate, Outlet, useLocation } from "react-router";
import { queryClient } from "./queryClient";
import { api, configureRequestContext } from "./api";
import type { CurrentUser, WorkspaceSummary } from "./types";

const WORKSPACE_STORAGE_KEY = "mil:active-workspace";
const development = import.meta.env.DEV && import.meta.env.VITE_AUTH_MODE === "disabled";
interface AuthState {
  loading: boolean;
  user: CurrentUser | null;
  workspaces: WorkspaceSummary[];
  workspace: WorkspaceSummary | null;
  sessionExpired: boolean;
  signIn(login: string, password: string): Promise<void>;
  signOut(): Promise<void>;
  changePassword(current: string, next: string): Promise<void>;
  switchWorkspace(id: string): void;
}
const AuthContext = createContext<AuthState | null>(null);
export function AuthProvider({ children }: { children: ReactNode }) {
  const [loading, setLoading] = useState(Boolean(development));
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [workspaces, setWorkspaces] = useState<WorkspaceSummary[]>([]);
  const [workspace, setWorkspace] = useState<WorkspaceSummary | null>(null);
  const [sessionExpired, setSessionExpired] = useState(false);
  const token = useRef<string | null>(null);
  const generation = useRef(0);
  function clear() {
    generation.current += 1;
    token.current = null;
    configureRequestContext(null, null);
    queryClient.clear();
    setUser(null); setWorkspaces([]); setWorkspace(null); setLoading(false);
  }
  async function hydrate(nextToken: string | null) {
    const expected = ++generation.current;
    token.current = nextToken;
    configureRequestContext(nextToken, null);
    try {
      const [profile, available] = await Promise.all([api.currentUser(), api.workspaces()]);
      if (generation.current !== expected) return;
      const stored = window.localStorage.getItem(WORKSPACE_STORAGE_KEY);
      const selected = available.find((item) => item.id === stored) ?? available[0] ?? null;
      configureRequestContext(nextToken, selected?.id ?? null);
      setUser(profile); setWorkspaces(available); setWorkspace(selected); setSessionExpired(false);
    } catch (error) {
      if (generation.current === expected) clear();
      throw error;
    } finally { setLoading(false); }
  }
  useEffect(() => {
    configureRequestContext(null, null);
    const expired = () => { clear(); setSessionExpired(true); };
    window.addEventListener("mil:session-expired", expired);
    if (development) void hydrate(null).catch(() => undefined);
    return () => {
      generation.current += 1;
      token.current = null;
      configureRequestContext(null, null);
      window.removeEventListener("mil:session-expired", expired);
    };
  }, []);
  const value = useMemo<AuthState>(() => ({
    loading, user, workspaces, workspace, sessionExpired,
    signIn: async (login, password) => {
      clear();
      const expected = generation.current;
      const result = await api.login(login, password);
      if (generation.current !== expected) return;
      await hydrate(result.access_token);
    },
    signOut: async () => {
      // Preserve the token for retry if server-side revocation fails.
      await api.logout();
      clear();
      window.localStorage.removeItem(WORKSPACE_STORAGE_KEY);
    },
    changePassword: async (current, next) => {
      await api.changePassword(current, next);
      clear();
    },
    switchWorkspace: (id) => {
      const selected = workspaces.find((item) => item.id === id) ?? null;
      if (!selected) return;
      window.localStorage.setItem(WORKSPACE_STORAGE_KEY, selected.id);
      configureRequestContext(token.current, selected.id);
      setWorkspace(selected);
      void queryClient.resetQueries();
    },
  }), [loading, user, workspaces, workspace, sessionExpired]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
export function ProtectedRoute() {
  const { loading, user } = useAuth();
  const location = useLocation();
  if (loading) return <main><p>Checking session…</p></main>;
  if (!user) return <Navigate to="/sign-in" replace state={{ from: location.pathname }} />;
  return <Outlet />;
}
