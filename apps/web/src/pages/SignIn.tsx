import { useRef, useState, type FormEvent } from "react";
import { Link, Navigate } from "react-router";
import { AuthFlowError, useAuth } from "../auth";

function safeSignInMessage(error: unknown) {
  if (error instanceof AuthFlowError) {
    return error.code === "no_workspace"
      ? "Your account does not have access to a research workspace. Contact the administrator."
      : "Your authenticated account has not been provisioned for this application.";
  }
  const message = error instanceof Error ? error.message.toLowerCase() : "";
  if (message.includes("email not confirmed")) return "Confirm your email before signing in.";
  if (message.includes("invalid login credentials")) return "Incorrect email or password.";
  if (message.includes("failed to fetch") || message.includes("network")) {
    return "Cannot reach the authentication service. Check your connection and HTTPS address.";
  }
  return "Sign-in could not be completed. Please try again or contact the administrator.";
}

export function SignIn() {
  const auth = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const errorRef = useRef<HTMLParagraphElement>(null);
  if (auth.user) return <Navigate to="/" replace />;
  async function submit(event: FormEvent) {
    event.preventDefault(); setError(""); setPending(true);
    try { await auth.signIn(email, password); }
    catch (reason) {
      setError(safeSignInMessage(reason));
      requestAnimationFrame(() => errorRef.current?.focus());
    } finally { setPending(false); }
  }
  return <main className="auth-page"><div className="auth-brand">
      <img src="/assets/branding/market-intelligence-lab-logo-512.webp" alt="Market Intelligence Lab" />
      <div><span>Market Intelligence Lab</span><small>Private research workspace</small></div>
    </div><h1>Sign in</h1>
    {auth.sessionExpired && <p role="alert">Your session expired. Please sign in again.</p>}
    {error && <p ref={errorRef} role="alert" tabIndex={-1}>{error}</p>}
    <form onSubmit={submit} aria-busy={pending}><label>Email<input autoComplete="email" inputMode="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required /></label>
      <label>Password<input autoComplete="current-password" type={showPassword ? "text" : "password"} value={password} onChange={(e) => setPassword(e.target.value)} required /></label>
      <button className="password-toggle" type="button" aria-pressed={showPassword} onClick={() => setShowPassword(value => !value)}>{showPassword ? "Hide password" : "Show password"}</button>
      <button type="submit" disabled={pending}>{pending ? "Signing in…" : "Sign in"}</button></form><Link to="/reset-password">Reset password</Link>
  </main>;
}
