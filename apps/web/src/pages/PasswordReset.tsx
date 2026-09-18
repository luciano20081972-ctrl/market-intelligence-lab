import { useState, type FormEvent } from "react";
import { Link } from "react-router";
import { useAuth } from "../auth";
export function PasswordReset() {
  const auth = useAuth();
  const [current, setCurrent] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  async function change(event: FormEvent) {
    event.preventDefault();
    try {
      await auth.changePassword(current, password);
      setMessage("Password changed. Sign in again; previous sessions have been revoked.");
    } catch { setMessage("Password change failed. Check your current password or try again later."); }
    finally { setCurrent(""); setPassword(""); }
  }
  return <main className="auth-page"><h1>Password recovery</h1>
    <p>Contact the MIL operator to arrange a secure credential reset. Email recovery is not available.</p>
    {message && <p role="status">{message}</p>}
    {auth.user && <form onSubmit={change}>
      <label>Current password<input type="password" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} required /></label>
      <label>New password<input type="password" autoComplete="new-password" minLength={15} maxLength={128} value={password} onChange={(e) => setPassword(e.target.value)} required /></label>
      <button>Change password</button>
    </form>}<Link to="/sign-in">Return to sign in</Link>
  </main>;
}
