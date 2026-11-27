"use client";

import Link from "next/link";
import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { apiGet, downloadUrl } from "@/lib/api";
import { asAtQuery, useOrg } from "@/components/OrgContext";
import { ReportingDate } from "@/components/ReportingDate";
import { AddInvoice } from "@/components/AddInvoice";
import { Empty, ErrorNotice, Loading, Money, StatusBadge, useLoad } from "@/components/ui";
import { BUCKET_LABELS, formatDate } from "@/lib/format";

function Invoices() {
  const { base, asAt, org, can } = useOrg();
  const params = useSearchParams();
  const [status, setStatus] = useState(params.get("status") || "");
  const [q, setQ] = useState("");
  const [dueFrom, setDueFrom] = useState("");
  const [dueTo, setDueTo] = useState("");
  const query = new URLSearchParams();
  if (asAt) query.set("as_at", asAt);
  if (status) query.set("status", status);
  if (q) query.set("q", q);
  if (dueFrom) query.set("due_from", dueFrom);
  if (dueTo) query.set("due_to", dueTo);
  const qs = query.toString();
  const { data, error, loading, reload } = useLoad(() => apiGet(`${base}/invoices?${qs}`), [base, qs]);
  const [adding, setAdding] = useState(false);

  return (
    <>
      <div className="page-head">
        <div><h1>Invoices</h1><div className="sub">{data ? `As at ${formatDate(data.reporting_date)} · ${data.items.length} invoices` : " "}</div></div>
        <div className="toolbar">
          <ReportingDate shown={data?.reporting_date} />
          {can("export") && <a className="btn" href={downloadUrl(`${base}/exports/invoices.csv${asAtQuery(asAt)}`)}>Export CSV</a>}
          {can("create_invoice") && <button className={adding ? "" : "primary"} onClick={() => setAdding(!adding)}>{adding ? "Close" : "Add invoice"}</button>}
        </div>
      </div>
      {adding && <div style={{ maxWidth: 560 }}><AddInvoice onCreated={reload} /></div>}
      <div className="panel">
        <div className="inline">
          <div className="field"><label htmlFor="q">Search</label><input id="q" placeholder="Invoice number or customer" value={q} onChange={(e) => setQ(e.target.value)} /></div>
          <div className="field"><label htmlFor="s">Status</label>
            <select id="s" value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="">All</option><option value="outstanding">Outstanding</option><option value="overdue">Overdue</option>
              <option value="open">Open (not overdue)</option><option value="paid">Paid</option><option value="disputed">Disputed</option>
              <option value="cancelled">Cancelled</option><option value="void">Void</option><option value="exception">Needs review</option>
            </select></div>
          <div className="field"><label htmlFor="df">Due from</label><input id="df" type="date" value={dueFrom} onChange={(e) => setDueFrom(e.target.value)} /></div>
          <div className="field"><label htmlFor="dt">Due to</label><input id="dt" type="date" value={dueTo} onChange={(e) => setDueTo(e.target.value)} /></div>
        </div>
      </div>
      <ErrorNotice error={error} />
      <div className="panel flush">
        {loading && !data ? <Loading /> : !data?.items.length ? <Empty>No invoices match. <Link href={`/o/${org.id}/imports`}>Import invoices</Link></Empty> : (
          <div className="table-wrap"><table>
            <thead><tr><th>Invoice</th><th>Customer</th><th>Issued</th><th>Due</th><th className="num">Original</th>
              <th className="num">Payments</th><th className="num">Credits</th><th className="num">Balance</th><th>Status</th><th>Ageing</th></tr></thead>
            <tbody>{data.items.map((i: any) => (
              <tr key={i.id}>
                <td><Link href={`/o/${org.id}/invoices/${i.id}`}>{i.invoice_number}</Link></td>
                <td><Link href={`/o/${org.id}/customers/${i.customer_id}`}>{i.customer_name}</Link></td>
                <td>{formatDate(i.issue_date)}</td><td>{formatDate(i.due_date)}</td>
                <td className="num"><Money value={i.original_amount} /></td><td className="num"><Money value={i.payments_allocated} /></td>
                <td className="num"><Money value={i.credits_allocated} /></td><td className="num"><Money value={i.balance} strong /></td>
                <td><StatusBadge status={i.status} />{i.source_differs && <span className="badge warn" title={`Source says ${i.source_amount_due} due`} style={{ marginLeft: 4 }}>source differs</span>}</td>
                <td className="small">{i.ageing_bucket ? `${BUCKET_LABELS[i.ageing_bucket]}${i.days_past_due ? ` (${i.days_past_due}d)` : ""}` : "—"}</td>
              </tr>))}</tbody>
          </table></div>
        )}
      </div>
      <p className="def">Balance = original amount − confirmed payments − confirmed credits dated on or before the reporting date. "Source differs" means your accounting export reported a different amount due; Vittasynx uses only allocations recorded here.</p>
    </>
  );
}

export default function Page() {
  return <Suspense><Invoices /></Suspense>;
}
