"use client";

import Link from "next/link";
import { useState } from "react";
import { apiGet, apiSend } from "@/lib/api";
import { useOrg } from "@/components/OrgContext";
import { Empty, ErrorNotice, Loading, Money, useAction, useLoad } from "@/components/ui";
import { formatDate } from "@/lib/format";

export default function Customers() {
  const { base, asAt, org, can } = useOrg();
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("active");
  const qs = new URLSearchParams({ ...(q && { q }), ...(status && { status }), ...(asAt && { as_at: asAt }) }).toString();
  const { data, error, loading, reload } = useLoad(() => apiGet(`${base}/customers?${qs}`), [base, qs]);
  const [form, setForm] = useState({ name: "", code: "" });
  const act = useAction();

  return (
    <>
      <div className="page-head">
        <div><h1>Customers</h1><div className="sub">{data ? `Balances as at ${formatDate(data.reporting_date)}` : " "}</div></div>
      </div>
      <div className="grid-3">
        <div>
          <div className="panel">
            <div className="inline">
              <div className="field"><label htmlFor="q">Search</label><input id="q" placeholder="Name or code" value={q} onChange={(e) => setQ(e.target.value)} /></div>
              <div className="field"><label htmlFor="st">Status</label><select id="st" value={status} onChange={(e) => setStatus(e.target.value)}>
                <option value="active">Active</option><option value="inactive">Inactive</option><option value="">All</option></select></div>
            </div>
          </div>
          <ErrorNotice error={error} />
          <div className="panel flush">
            {loading && !data ? <Loading /> : !data?.items.length ? <Empty>No customers yet. They are created when you import invoices, or add one here.</Empty> : (
              <div className="table-wrap"><table>
                <thead><tr><th>Customer</th><th>Code</th><th className="num">Outstanding</th><th className="num">Overdue</th><th className="num">Unapplied</th></tr></thead>
                <tbody>{data.items.map((c: any) => (
                  <tr key={c.id}><td><Link href={`/o/${org.id}/customers/${c.id}`}>{c.name}</Link></td><td className="mono">{c.code ?? "—"}</td>
                    <td className="num"><Money value={c.total_outstanding} /></td><td className="num"><Money value={c.overdue} /></td>
                    <td className="num"><Money value={c.unapplied_payments} /></td></tr>))}</tbody>
              </table></div>
            )}
          </div>
        </div>
        {can("manage_customers") && (
          <div className="panel">
            <h2>Add a customer</h2>
            <ErrorNotice error={act.error} />
            <form onSubmit={async (e) => { e.preventDefault(); if (await act.run(() => apiSend("POST", `${base}/customers`, { name: form.name, code: form.code || null }))) { setForm({ name: "", code: "" }); reload(); } }}>
              <div className="field"><label htmlFor="cn">Name</label><input id="cn" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
              <div className="field"><label htmlFor="cc">Customer code (from your accounting system)</label><input id="cc" value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} /></div>
              <button className="primary" disabled={act.busy}>Add customer</button>
            </form>
            <p className="def">Imports match customers by code first, then by exact name. Using codes avoids mismatches.</p>
          </div>
        )}
      </div>
    </>
  );
}
