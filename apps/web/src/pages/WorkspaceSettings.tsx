import { useQuery } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { api } from "../api";
import { useAuth } from "../auth";

export function WorkspaceSettings() {
  const auth = useAuth(); const id = auth.workspace?.id ?? "";
  const members = useQuery({ queryKey: ["members", id], queryFn: () => api.workspaceMembers(id), enabled: Boolean(id) });
  const [email, setEmail] = useState(""); const [role, setRole] = useState("member");
  const canManage = auth.workspace?.role === "owner" || auth.workspace?.role === "admin";
  async function invite(event: FormEvent) { event.preventDefault(); await api.inviteMember(id, email, role); setEmail(""); }
  return <section><h1>Workspace settings</h1><p>{auth.workspace?.name} · Your role: <b>{auth.workspace?.role}</b></p>
    <h2>Members</h2>{members.data?.map((member) => <p key={member.id}>{member.email} — {member.role}</p>)}
    {canManage ? <form onSubmit={invite}><label>Email<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required /></label>
      <label>Role<select value={role} onChange={(event) => setRole(event.target.value)}><option>admin</option><option>member</option><option>viewer</option></select></label><button>Invite member</button></form>
      : <p>Member management requires administrator permission.</p>}</section>;
}
