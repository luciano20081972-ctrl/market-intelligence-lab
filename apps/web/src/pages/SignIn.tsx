import { useState, type FormEvent } from "react";
import { Link, Navigate } from "react-router";
import { useAuth } from "../auth";

export function SignIn() {
  const auth = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  if (auth.user) return <Navigate to="/" replace />;
  async function submit(event: FormEvent) {
    event.preventDefault(); setError("");
    try { await auth.signIn(email, password); } catch { setError("Sign-in failed. Check your credentials and verification state."); }
  }
  return <main className="auth-page"><div className="auth-brand">
      <img src="/assets/branding/market-intelligence-lab-logo-512.webp" alt="Market Intelligence Lab" />
      <div><span>Market Intelligence Lab</span><small>Private research workspace</small></div>
    </div><h1>Sign in</h1>
    {auth.sessionExpired && <p role="alert">Your session expired. Please sign in again.</p>}
    {error && <p role="alert">{error}</p>}
    <form onSubmit={submit}><label>Email<input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required /></label>
      <label>Password<input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required /></label>
      <button type="submit">Sign in</button></form><Link to="/reset-password">Reset password</Link>
  </main>;
}
