"use client";

import Link from "next/link";
import { useState } from "react";
import { useParams } from "next/navigation";
import { apiGet, apiSend } from "@/lib/api";
import { asAtQuery, useOrg } from "@/components/OrgContext";
import { Badge, ErrorNotice, Loading, Money, StatusBadge, useAction, useLoad } from "@/components/ui";
import { BUCKET_LABELS, formatDate, formatDateTime } from "@/lib/format";

export default function InvoiceDetail() {
  const { invoiceId } = useParams<{ invoiceId: string }>();
  const { base, asAt, org, can } = useOrg();
  const { data: inv, error, reload } = useLoad(() => apiGet(`${base}/invoices/${invoiceId}${asAtQuery(asAt)}`), [base, invoiceId, asAt]);
  const act = useAction();
  const [reason, setReason] = useState("");
  const [newStatus, setNewStatus] = useState("");

  if (error) return <ErrorNotice error={error} />;
  if (!inv) return <Loading />;
  const transitions: Record<string, string[]> = { open: ["disputed", "cancelled", "void"], disputed: ["open", "cancelled", "void"] };

  return (
    <>
      <div className="page-head">
        <div>
          <div className="small"><Link href={`/o/${org.id}/invoices`}>Invoices</Link> /</div>
          <h1>Invoice {inv.invoice_number} <StatusBadge status={inv.status} /></h1>
          <div className="sub"><Link href={`/o/${org.id}/customers/${inv.customer_id}`}>{inv.customer_name}</Link> · balance as at {formatDate(inv.reporting_date)}</div>
        </div>
      </div>
      <div className="figures">
        <div className="figure"><div className="label">Original amount</div><div className="value"><Money value={inv.original_amount} /></div>
          <div className="note">{inv.total_is_derived ? "Derived from net + tax" : "Incl. tax"}</div></div>
        <div className="figure"><div className="label">Payments allocated</div><div className="value"><Money value={inv.payments_allocated} /></div></div>
        <div className="figure"><div className="label">Credits allocated</div><div className="value"><Money value={inv.credits_allocated} /></div></div>
        <div className="figure"><div className="label">Balance</div><div className="value"><Money value={inv.balance} /></div>
          <div className="note">{inv.ageing_bucket ? `${BUCKET_LABELS[inv.ageing_bucket]} · ${inv.days_past_due} days past due` : " "}</div></div>
      </div>
      <div className="grid-3">
        <div>
          <div className="panel flush">
            <div className="panel-head"><h2>Allocations</h2></div>
            {inv.allocations.length === 0 ? <div className="empty">No payments or credits allocated yet.</div> : (
              <table><thead><tr><th>Effective date</th><th>Source</th><th className="num">Amount</th><th>Status</th><th /></tr></thead>
                <tbody>{inv.allocations.map((a: any) => (
                  <tr key={a.id}>
                    <td>{formatDate(a.effective_date)}</td>
                    <td>{a.payment_id ? <Link href={`/o/${org.id}/payments/${a.payment_id}`}>Payment</Link> : <Link href={`/o/${org.id}/credit-notes/${a.credit_note_id}`}>Credit note</Link>}</td>
                    <td className="num"><Money value={a.amount} /></td>
                    <td><Badge kind={a.status === "reversed" ? "reversed" : "paid"}>{a.status}</Badge>{a.reversal_reason && <div className="small muted">{a.reversal_reason}</div>}</td>
                    <td>{a.status === "confirmed" && can("reverse_allocation") && (
                      <button className="small danger" disabled={act.busy} onClick={async () => {
                        const why = window.prompt("Reason for reversing this allocation?");
                        if (why && await act.run(() => apiSend("POST", `${base}/allocations/${a.id}/reverse`, { reason: why }))) reload();
                      }}>Reverse</button>)}</td>
                  </tr>))}</tbody></table>
            )}
          </div>
          <div className="panel flush">
            <div className="panel-head"><h2>Versions</h2><span className="muted small">Every change is kept</span></div>
            <table><thead><tr><th>#</th><th>When</th><th>Change</th><th className="num">Amount</th><th>Due</th></tr></thead>
              <tbody>{inv.versions.map((v: any) => (
                <tr key={v.version}><td>{v.version}</td><td className="small">{formatDateTime(v.created_at)}</td><td className="small">{v.reason}</td>
                  <td className="num"><Money value={v.values.total_amount} /></td><td>{formatDate(v.values.due_date)}</td></tr>))}</tbody></table>
          </div>
          <div className="panel">
            <h2>History</h2>
            {inv.history.map((h: any, i: number) => (
              <div key={i} className="small" style={{ padding: "4px 0", borderBottom: "1px solid var(--line)" }}>
                <strong>{h.action}</strong> · {formatDateTime(h.at)}{h.note ? ` · ${h.note}` : ""}
              </div>))}
          </div>
        </div>
        <div>
          <div className="panel">
            <h2>Details</h2>
            <dl className="kv">
              <dt>Issue date</dt><dd>{formatDate(inv.issue_date)}</dd>
              <dt>Due date</dt><dd>{formatDate(inv.due_date)}</dd>
              <dt>Tax</dt><dd><Money value={inv.tax_amount} /></dd>
              <dt>Net</dt><dd><Money value={inv.net_amount} /></dd>
              <dt>Reference</dt><dd>{inv.reference ?? "—"}</dd>
              <dt>Source amount due</dt><dd><Money value={inv.source_amount_due} />{inv.source_differs && <div className="small" style={{ color: "var(--warn)" }}>Differs from calculated balance</div>}</dd>
              <dt>Version</dt><dd>{inv.version}</dd>
              {inv.status_reason && <><dt>Status reason</dt><dd>{inv.status_reason}</dd></>}
            </dl>
          </div>
          {can("manage_credits_and_status") && transitions[inv.stored_status] && (
            <div className="panel">
              <h2>Change status</h2>
              <ErrorNotice error={act.error} />
              <div className="field"><label htmlFor="ns">New status</label>
                <select id="ns" value={newStatus} onChange={(e) => setNewStatus(e.target.value)}>
                  <option value="">Choose…</option>{transitions[inv.stored_status].map((s) => <option key={s} value={s}>{s}</option>)}</select></div>
              <div className="field"><label htmlFor="r">Reason (recorded in the audit log)</label><input id="r" value={reason} onChange={(e) => setReason(e.target.value)} /></div>
              <button disabled={!newStatus || !reason || act.busy} onClick={async () => {
                if (await act.run(() => apiSend("POST", `${base}/invoices/${invoiceId}/status`, { status: newStatus, reason }))) { setReason(""); setNewStatus(""); reload(); }
              }}>Update status</button>
              <p className="def">Cancelled and void invoices are excluded from receivables. Disputed invoices stay in receivables but are excluded from payment-behaviour metrics.</p>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
