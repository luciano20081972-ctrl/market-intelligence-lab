import { useState, type FormEvent } from "react";
import { useAuth } from "../auth";
import { api } from "../api";

export function UserProfile() {
  const auth = useAuth(); const [name, setName] = useState(auth.user?.display_name ?? ""); const [saved, setSaved] = useState(false);
  async function submit(event: FormEvent) { event.preventDefault(); await api.updateCurrentUser(name); setSaved(true); }
  return <section><h1>User profile</h1><p>{auth.user?.email} · {auth.user?.email_verified ? "Email verified" : "Email not verified"}</p>
    <form onSubmit={submit}><label>Display name<input value={name} onChange={(event) => setName(event.target.value)} /></label><button>Save profile</button></form>{saved && <p role="status">Profile saved.</p>}</section>;
}
