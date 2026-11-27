"use client";

import { useState } from "react";
import { apiGet, apiSend } from "@/lib/api";
import { useOrg } from "@/components/OrgContext";
import { Badge, ErrorNotice, Loading, useAction, useLoad } from "@/components/ui";
import { formatDate } from "@/lib/format";

const ROLES = [
  ["admin", "Administrator"], ["finance_manager", "Finance Manager"], ["ar_officer", "Accounts Receivable Officer"], ["read_only", "Read-only User"],
];

export default function Members() {
  const { base, me, can } = useOrg();
  const members = useLoad(() => apiGet(`${base}/members`), [base]);
  const invites = useLoad(() => (can("manage_members") ? apiGet(`${base}/invitations`) : Promise.resolve({ items: [] })), [base]);
  const [form, setForm] = useState({ email: "", role: "ar_officer" });
  const act = useAction();
  const reload = () => { members.reload(); invites.reload(); };

  return (
    <>
      <div className="page-head"><div><h1>Members</h1><div className="sub">Roles decide what each person can do; the server enforces them.</div></div></div>
      <ErrorNotice error={members.error || act.error} />
      <div className="grid-3">
        <div className="panel flush">
          {!members.data ? <Loading /> : (
            <table><thead><tr><th>Name</th><th>Role</th><th>2FA</th><th>Joined</th>{can("manage_members") && <th />}</tr></thead>
              <tbody>{members.data.items.map((m: any) => (
                <tr key={m.user_id}><td>{m.full_name}<div className="small muted">{m.email}</div></td>
                  <td>{can("manage_members") && m.role !== "owner" && m.user_id !== me.user.id ? (
                    <select value={m.role} onChange={async (e) => { if (await act.run(() => apiSend("PATCH", `${base}/members/${m.user_id}`, { role: e.target.value }))) reload(); }}>
                      {ROLES.map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>) : m.role_label}</td>
                  <td>{m.mfa_enabled ? <Badge kind="paid">On</Badge> : <Badge>Off</Badge>}</td><td>{formatDate(m.joined_at)}</td>
                  {can("manage_members") && <td>{m.role !== "owner" && m.user_id !== me.user.id && (
                    <button className="small danger" onClick={async () => { if (window.confirm(`Remove ${m.full_name}? They lose access immediately.`) && await act.run(() => apiSend("DELETE", `${base}/members/${m.user_id}`))) reload(); }}>Remove</button>)}</td>}
                </tr>))}</tbody></table>
          )}
        </div>
        {can("manage_members") && (
          <div>
            <div className="panel">
              <h2>Invite someone</h2>
              <form onSubmit={async (e) => { e.preventDefault(); if (await act.run(() => apiSend("POST", `${base}/invitations`, form))) { setForm({ email: "", role: "ar_officer" }); reload(); } }}>
                <div className="field"><label htmlFor="e">Email</label><input id="e" type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></div>
                <div className="field"><label htmlFor="r">Role</label><select id="r" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
                  {ROLES.map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></div>
                <button className="primary" disabled={act.busy}>Send invitation</button>
              </form>
              <p className="def">The invitee must sign in with this exact, verified email address. Invitations expire after 7 days.</p>
            </div>
            {(invites.data?.items.length ?? 0) > 0 && (
              <div className="panel"><h3>Pending invitations</h3>
                {invites.data.items.map((i: any) => (
                  <div key={i.id} className="small" style={{ display: "flex", justifyContent: "space-between", padding: "4px 0" }}>
                    <span>{i.email} · {i.role.replace("_", " ")}</span>
                    <button className="link small" onClick={async () => { if (await act.run(() => apiSend("DELETE", `${base}/invitations/${i.id}`))) reload(); }}>Revoke</button></div>))}
              </div>
            )}
          </div>
        )}
      </div>
    </>
  );
}
