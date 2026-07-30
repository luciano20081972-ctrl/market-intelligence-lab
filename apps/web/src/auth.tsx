import { createClient, type Session, type SupabaseClient } from "@supabase/supabase-js";
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { Navigate, Outlet, useLocation } from "react-router-dom";
import { queryClient } from "./queryClient";
import { api, configureRequestContext } from "./api";
import type { CurrentUser, WorkspaceSummary } from "./types";

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL as string | undefined;
const supabaseKey = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY as string | undefined;
const supabase: SupabaseClient | null = supabaseUrl && supabaseKey
  ? createClient(supabaseUrl, supabaseKey)
  : null;
const WORKSPACE_STORAGE_KEY = "mil:active-workspace";

interface AuthState {
  loading: boolean;
  user: CurrentUser | null;
  workspaces: WorkspaceSummary[];
  workspace: WorkspaceSummary | null;
  sessionExpired: boolean;
  signIn(email: string, password: string): Promise<void>;
  signOut(): Promise<void>;
  requestReset(email: string): Promise<void>;
  completeReset(password: string): Promise<void>;
  switchWorkspace(id: string): void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [loading, setLoading] = useState(true);
  const [session, setSession] = useState<Session | null>(null);
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [workspaces, setWorkspaces] = useState<WorkspaceSummary[]>([]);
  const [workspace, setWorkspace] = useState<WorkspaceSummary | null>(null);
  const [sessionExpired, setSessionExpired] = useState(false);

  async function hydrate(nextSession: Session | null) {
    const development = supabase === null;
    if (!development && !nextSession) {
      configureRequestContext(null, null);
      setUser(null); setWorkspaces([]); setWorkspace(null); setLoading(false);
      return;
    }
    configureRequestContext(nextSession?.access_token ?? null, null);
    try {
      const [profile, available] = await Promise.all([api.currentUser(), api.workspaces()]);
      const storedWorkspaceId = window.localStorage.getItem(WORKSPACE_STORAGE_KEY);
      const selected = available.find((item) => item.id === storedWorkspaceId)
        ?? available[0]
        ?? null;
      if (selected) window.localStorage.setItem(WORKSPACE_STORAGE_KEY, selected.id);
      else window.localStorage.removeItem(WORKSPACE_STORAGE_KEY);
      configureRequestContext(nextSession?.access_token ?? null, selected?.id ?? null);
      setUser(profile); setWorkspaces(available); setWorkspace(selected); setSessionExpired(false);
    } catch {
      setUser(null); setWorkspaces([]); setWorkspace(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const onExpired = () => { setSessionExpired(true); setUser(null); queryClient.clear(); };
    window.addEventListener("mil:session-expired", onExpired);
    if (!supabase) void hydrate(null);
    else {
      void supabase.auth.getSession().then(({ data }) => { setSession(data.session); void hydrate(data.session); });
      const { data } = supabase.auth.onAuthStateChange((_event, next) => {
        setSession(next); void hydrate(next);
      });
      return () => { data.subscription.unsubscribe(); window.removeEventListener("mil:session-expired", onExpired); };
    }
    return () => window.removeEventListener("mil:session-expired", onExpired);
  }, []);

  const value = useMemo<AuthState>(() => ({
    loading, user, workspaces, workspace, sessionExpired,
    signIn: async (email, password) => {
      if (!supabase) { await hydrate(null); return; }
      const { data, error } = await supabase.auth.signInWithPassword({ email, password });
      if (error) { await api.auditAuth("auth.sign_in_failed", "failure"); throw error; }
      configureRequestContext(data.session?.access_token ?? null, null);
      await api.auditAuth("auth.sign_in_succeeded", "success");
    },
    signOut: async () => {
      await api.auditAuth("auth.signed_out", "success").catch(() => undefined);
      if (supabase) await supabase.auth.signOut();
      window.localStorage.removeItem(WORKSPACE_STORAGE_KEY);
      configureRequestContext(null, null); queryClient.clear(); setUser(null); setWorkspace(null);
    },
    requestReset: async (email) => {
      if (!supabase) return;
      const { error } = await supabase.auth.resetPasswordForEmail(email, {
        redirectTo: `${window.location.origin}/reset-password`,
      });
      if (error) throw error;
      await api.auditAuth("auth.password_reset_requested", "success");
    },
    completeReset: async (password) => {
      if (!supabase) return;
      const { error } = await supabase.auth.updateUser({ password });
      if (error) throw error;
      await api.auditAuth("auth.password_reset_completed", "success");
    },
    switchWorkspace: (id) => {
      const selected = workspaces.find((item) => item.id === id) ?? null;
      if (selected) window.localStorage.setItem(WORKSPACE_STORAGE_KEY, selected.id);
      else window.localStorage.removeItem(WORKSPACE_STORAGE_KEY);
      configureRequestContext(session?.access_token ?? null, selected?.id ?? null);
      setWorkspace(selected);
      void queryClient.resetQueries();
    },
  }), [loading, user, workspaces, workspace, sessionExpired, session]);
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
  if (loading) return <main><p>Restoring secure session…</p></main>;
  if (!user) return <Navigate to="/sign-in" replace state={{ from: location.pathname }} />;
  return <Outlet />;
}
