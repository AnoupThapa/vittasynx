"use client";

import Link from "next/link";
import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { apiGet, apiSend } from "@/lib/api";
import { useOrg } from "@/components/OrgContext";
import { Badge, Empty, ErrorNotice, Loading, Money, useAction, useLoad } from "@/components/ui";
import { formatDate } from "@/lib/format";

function Payments() {
  const { base, org, can } = useOrg();
  const params = useSearchParams();
  const [filter, setFilter] = useState(params.get("unapplied") ? "unapplied" : "");
  const qs = filter === "unapplied" ? "?unapplied_only=true" : filter === "unassigned" ? "?unassigned_only=true" : "";
  const { data, error, loading, reload } = useLoad(() => apiGet(`${base}/payments${qs}`), [base, qs]);
  const customers = useLoad(() => apiGet(`${base}/customers`), [base]);
  const [form, setForm] = useState({ customer_id: "", payment_date: "", amount: "", reference: "", method: "" });
  const act = useAction();

  return (
    <>
      <div className="page-head"><div><h1>Payments</h1><div className="sub">Customer receipts, manual or imported</div></div>
        <div className="toolbar"><select value={filter} onChange={(e) => setFilter(e.target.value)} aria-label="Filter">
          <option value="">All payments</option><option value="unapplied">With unapplied amount</option><option value="unassigned">Unassigned bank receipts</option></select></div></div>
      <div className="grid-3">
        <div>
          <ErrorNotice error={error} />
          <div className="panel flush">
            {loading && !data ? <Loading /> : !data?.items.length ? <Empty>No payments. Record one, or import a payments or bank file.</Empty> : (
              <div className="table-wrap"><table>
                <thead><tr><th>Date</th><th>Customer</th><th>Reference</th><th>Source</th><th className="num">Amount</th><th className="num">Unapplied</th></tr></thead>
                <tbody>{data.items.map((p: any) => (
                  <tr key={p.id}><td><Link href={`/o/${org.id}/payments/${p.id}`}>{formatDate(p.payment_date)}</Link></td>
                    <td>{p.customer_name ?? <Badge kind="warn">Unassigned</Badge>}</td><td className="small">{p.reference ?? p.description ?? "—"}</td>
                    <td className="small">{p.source}</td><td className="num"><Money value={p.amount} /></td><td className="num"><Money value={p.unapplied} /></td></tr>))}</tbody>
              </table></div>
            )}
          </div>
        </div>
        {can("record_payment") && (
          <div className="panel">
            <h2>Record a payment</h2>
            <ErrorNotice error={act.error} />
            <form onSubmit={async (e) => { e.preventDefault(); const p = await act.run(() => apiSend("POST", `${base}/payments`, { ...form, reference: form.reference || null, method: form.method || null })); if (p) { setForm({ customer_id: "", payment_date: "", amount: "", reference: "", method: "" }); reload(); } }}>
              <div className="field"><label htmlFor="c">Customer</label><select id="c" required value={form.customer_id} onChange={(e) => setForm({ ...form, customer_id: e.target.value })}>
                <option value="">Select…</option>{customers.data?.items.map((c: any) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></div>
              <div className="field"><label htmlFor="d">Payment date</label><input id="d" type="date" required value={form.payment_date} onChange={(e) => setForm({ ...form, payment_date: e.target.value })} /></div>
              <div className="field"><label htmlFor="a">Amount ({org.currency})</label><input id="a" required inputMode="decimal" placeholder="0.00" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} /></div>
              <div className="field"><label htmlFor="r">Reference</label><input id="r" value={form.reference} onChange={(e) => setForm({ ...form, reference: e.target.value })} /></div>
              <div className="field"><label htmlFor="m">Method</label><input id="m" placeholder="EFT, card, cheque…" value={form.method} onChange={(e) => setForm({ ...form, method: e.target.value })} /></div>
              <button className="primary" disabled={act.busy}>Record payment</button>
            </form>
          </div>
        )}
      </div>
    </>
  );
}

export default function Page() {
  return <Suspense><Payments /></Suspense>;
}
