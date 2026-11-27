"use client";

import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { apiGet, apiSend } from "@/lib/api";
import { AuthCard, ErrorNotice, Loading, useAction, useLoad } from "@/components/ui";

const CURRENCIES = ["AUD", "NPR", "NZD", "USD", "GBP", "EUR", "INR", "SGD"];
const ZONES = ["Australia/Sydney", "Australia/Melbourne", "Australia/Brisbane", "Australia/Adelaide", "Australia/Perth",
  "Asia/Kathmandu", "Pacific/Auckland", "Asia/Singapore", "Asia/Kolkata", "Europe/London", "America/New_York", "UTC"];

export default function Orgs() {
  const router = useRouter();
  const me = useLoad(() => apiGet("/auth/me"), []);
  const [form, setForm] = useState({ name: "", currency: "AUD", timezone: "Australia/Sydney" });
  const { busy, error, run } = useAction();
  if (!me.data) return <Loading />;
  const orgs = me.data.organisations as any[];
  return (
    <AuthCard title={orgs.length ? "Your organisations" : "Set up your organisation"}>
      {orgs.length > 0 && (
        <div style={{ marginBottom: 20 }}>
          {orgs.map((o) => (
            <div key={o.id} style={{ display: "flex", justifyContent: "space-between", padding: "8px 0", borderBottom: "1px solid var(--line)" }}>
              <Link href={`/o/${o.id}/dashboard`}><strong>{o.name}</strong></Link>
              <span className="muted small">{o.role_label} · {o.currency}</span>
            </div>
          ))}
          <h3 style={{ marginTop: 20 }}>Create another organisation</h3>
        </div>
      )}
      <ErrorNotice error={error} />
      <form onSubmit={async (e) => { e.preventDefault(); const o = await run(() => apiSend("POST", "/orgs", form)); if (o) router.push(`/o/${o.id}/dashboard`); }}>
        <div className="field"><label htmlFor="n">Business name</label>
          <input id="n" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
        <div className="field"><label htmlFor="c">Reporting currency</label>
          <select id="c" value={form.currency} onChange={(e) => setForm({ ...form, currency: e.target.value })}>
            {CURRENCIES.map((c) => <option key={c}>{c}</option>)}</select>
          <div className="def">Fixed once created. Invoices in other currencies are rejected in this release.</div></div>
        <div className="field"><label htmlFor="t">Timezone</label>
          <select id="t" value={form.timezone} onChange={(e) => setForm({ ...form, timezone: e.target.value })}>
            {ZONES.map((z) => <option key={z}>{z}</option>)}</select>
          <div className="def">Decides which day "today" is when ageing invoices.</div></div>
        <button className="primary" disabled={busy}>Create organisation</button>
      </form>
    </AuthCard>
  );
}
