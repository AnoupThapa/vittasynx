"use client";

import Link from "next/link";
import { useState } from "react";
import { apiGet, apiSend } from "@/lib/api";
import { useOrg } from "@/components/OrgContext";
import { Empty, ErrorNotice, Loading, Money, useAction, useLoad } from "@/components/ui";
import { formatDate } from "@/lib/format";

export default function CreditNotes() {
  const { base, org, can } = useOrg();
  const { data, error, loading, reload } = useLoad(() => apiGet(`${base}/credit-notes`), [base]);
  const customers = useLoad(() => apiGet(`${base}/customers`), [base]);
  const blank = { customer_id: "", credit_note_number: "", credit_date: "", amount: "", reason: "", applies_to_invoice: "" };
  const [form, setForm] = useState(blank);
  const act = useAction();
  return (
    <>
      <div className="page-head"><div><h1>Credit notes</h1><div className="sub">Separate records, allocated to invoices like payments</div></div></div>
      <div className="grid-3">
        <div>
          <ErrorNotice error={error} />
          <div className="panel flush">
            {loading && !data ? <Loading /> : !data?.items.length ? <Empty>No credit notes.</Empty> : (
              <table><thead><tr><th>Number</th><th>Customer</th><th>Date</th><th>Reason</th><th className="num">Amount</th><th className="num">Unapplied</th></tr></thead>
                <tbody>{data.items.map((c: any) => (
                  <tr key={c.id}><td><Link href={`/o/${org.id}/credit-notes/${c.id}`}>{c.credit_note_number}</Link></td><td>{c.customer_name}</td>
                    <td>{formatDate(c.credit_date)}</td><td className="small">{c.reason ?? "—"}</td>
                    <td className="num"><Money value={c.amount} /></td><td className="num"><Money value={c.unapplied} /></td></tr>))}</tbody></table>
            )}
          </div>
        </div>
        {can("manage_credits_and_status") && (
          <div className="panel">
            <h2>Record a credit note</h2>
            <ErrorNotice error={act.error} />
            <form onSubmit={async (e) => { e.preventDefault(); if (await act.run(() => apiSend("POST", `${base}/credit-notes`, { ...form, reason: form.reason || null, applies_to_invoice: form.applies_to_invoice || null }))) { setForm(blank); reload(); } }}>
              <div className="field"><label htmlFor="c">Customer</label><select id="c" required value={form.customer_id} onChange={(e) => setForm({ ...form, customer_id: e.target.value })}>
                <option value="">Select…</option>{customers.data?.items.map((c: any) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></div>
              <div className="field"><label htmlFor="n">Credit note number</label><input id="n" required value={form.credit_note_number} onChange={(e) => setForm({ ...form, credit_note_number: e.target.value })} /></div>
              <div className="field"><label htmlFor="d">Date</label><input id="d" type="date" required value={form.credit_date} onChange={(e) => setForm({ ...form, credit_date: e.target.value })} /></div>
              <div className="field"><label htmlFor="a">Amount incl. tax ({org.currency})</label><input id="a" required inputMode="decimal" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} /></div>
              <div className="field"><label htmlFor="i">Applies to invoice (optional)</label><input id="i" value={form.applies_to_invoice} onChange={(e) => setForm({ ...form, applies_to_invoice: e.target.value })} /></div>
              <div className="field"><label htmlFor="r">Reason</label><input id="r" placeholder="e.g. damaged goods, write-off" value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} /></div>
              <button className="primary" disabled={act.busy}>Record credit note</button>
            </form>
          </div>
        )}
      </div>
    </>
  );
}
