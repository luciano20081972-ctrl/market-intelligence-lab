import { useState, type FormEvent } from "react";
import { useAuth } from "../auth";

export function PasswordReset() {
  const auth = useAuth(); const [email, setEmail] = useState(""); const [password, setPassword] = useState(""); const [message, setMessage] = useState("");
  async function request(event: FormEvent) { event.preventDefault(); await auth.requestReset(email); setMessage("If the account exists, password-reset instructions have been sent."); }
  async function complete(event: FormEvent) { event.preventDefault(); await auth.completeReset(password); setMessage("Password updated. You may return to sign in."); }
  return <main className="auth-page"><h1>Password reset</h1>{message && <p role="status">{message}</p>}
    <form onSubmit={request}><label>Email<input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required /></label><button>Request reset</button></form>
    <form onSubmit={complete}><label>New password<input type="password" minLength={12} value={password} onChange={(e) => setPassword(e.target.value)} required /></label><button>Complete reset</button></form>
  </main>;
}
