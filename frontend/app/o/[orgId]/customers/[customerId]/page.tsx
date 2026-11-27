"use client";

import Link from "next/link";
import { useState } from "react";
import { useParams } from "next/navigation";
import { apiGet, apiSend } from "@/lib/api";
import { asAtQuery, useOrg } from "@/components/OrgContext";
import { ReportingDate } from "@/components/ReportingDate";
import { Badge, Empty, ErrorNotice, Loading, Money, StatusBadge, useAction, useLoad } from "@/components/ui";
import { BUCKET_LABELS, formatDate } from "@/lib/format";

export default function CustomerDetail() {
  const { customerId } = useParams<{ customerId: string }>();
  const { base, asAt, org, can } = useOrg();
  const { data: c, error, reload } = useLoad(() => apiGet(`${base}/customers/${customerId}${asAtQuery(asAt)}`), [base, customerId, asAt]);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({ name: "", code: "" });
  const act = useAction();
  if (error) return <ErrorNotice error={error} />;
  if (!c) return <Loading />;
  const b = c.balances;
  const beh = c.behaviour;

  return (
    <>
      <div className="page-head">
        <div>
          <div className="small"><Link href={`/o/${org.id}/customers`}>Customers</Link> /</div>
          <h1>{c.name} {c.status === "inactive" && <Badge kind="void">Inactive</Badge>}</h1>
          <div className="sub">{c.code ? <span className="mono">{c.code}</span> : "No customer code"}</div>
        </div>
        <div className="toolbar">
          <ReportingDate shown={c.reporting_date} />
          {can("manage_customers") && !editing && <button onClick={() => { setForm({ name: c.name, code: c.code ?? "" }); setEditing(true); }}>Edit</button>}
        </div>
      </div>
      {editing && (
        <div className="panel">
          <ErrorNotice error={act.error} />
          <div className="inline">
            <div className="field"><label htmlFor="n">Name</label><input id="n" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
            <div className="field"><label htmlFor="cd">Code</label><input id="cd" value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} /></div>
            <button className="primary" disabled={act.busy} onClick={async () => { if (await act.run(() => apiSend("PATCH", `${base}/customers/${customerId}`, { name: form.name, code: form.code || null }))) { setEditing(false); reload(); } }}>Save</button>
            <button onClick={() => act.run(() => apiSend("PATCH", `${base}/customers/${customerId}`, { status: c.status === "active" ? "inactive" : "active" })).then(() => { setEditing(false); reload(); })}>
              Mark {c.status === "active" ? "inactive" : "active"}</button>
            <button className="link" onClick={() => setEditing(false)}>Cancel</button>
          </div>
        </div>
      )}
      {b && (
        <div className="figures">
          <div className="figure"><div className="label">Outstanding</div><div className="value"><Money value={b.total_outstanding} /></div></div>
          <div className="figure"><div className="label">Overdue</div><div className="value"><Money value={b.overdue} /></div></div>
          {(["current", "1_30", "31_60", "61_90", "91_plus"] as const).map((k) => (
            <div className="figure" key={k}><div className="label"><span className={`swatch b-${k}`} />{BUCKET_LABELS[k]}</div><div className="value" style={{ fontSize: 16 }}><Money value={b[k]} /></div></div>))}
          <div className="figure"><div className="label">Unapplied payments</div><div className="value" style={{ fontSize: 16 }}><Money value={b.unapplied_payments} /></div></div>
          <div className="figure"><div className="label">Unapplied credits</div><div className="value" style={{ fontSize: 16 }}><Money value={b.unapplied_credits} /></div></div>
        </div>
      )}
      <div className="grid-3">
        <div className="panel flush">
          <div className="panel-head"><h2>Invoice history</h2></div>
          {c.invoices.length === 0 ? <Empty>No invoices.</Empty> : (
            <div className="table-wrap"><table>
              <thead><tr><th>Invoice</th><th>Issued</th><th>Due</th><th className="num">Original</th><th className="num">Balance</th><th>Status</th></tr></thead>
              <tbody>{c.invoices.map((i: any) => (
                <tr key={i.id}><td><Link href={`/o/${org.id}/invoices/${i.id}`}>{i.invoice_number}</Link></td><td>{formatDate(i.issue_date)}</td><td>{formatDate(i.due_date)}</td>
                  <td className="num"><Money value={i.original_amount} /></td><td className="num"><Money value={i.balance} /></td><td><StatusBadge status={i.status} /></td></tr>))}</tbody>
            </table></div>
          )}
        </div>
        <div className="panel">
          <h2>Payment behaviour</h2>
          <p className="small muted">Observed history from {formatDate(beh.observation_start)} to {formatDate(beh.observation_end)}. Not a prediction or a credit rating.</p>
          {!beh.sufficient_data ? (
            <div className="notice info">{beh.insufficient_reason}</div>
          ) : (
            <dl className="kv">
              <dt>Invoices analysed</dt><dd>{beh.invoices_analysed}</dd>
              <dt>Average days to payment</dt><dd>{beh.average_days_to_payment}</dd>
              <dt>Average days late</dt><dd>{beh.average_days_late}</dd>
              <dt>Paid on time</dt><dd>{beh.on_time_percentage}%</dd>
              <dt>Payment days per month</dt><dd>{beh.payment_frequency_per_month}</dd>
            </dl>
          )}
          <p className="def">{beh.limitation} Minimum: {beh.minimum_invoices} fully paid invoices over at least {beh.minimum_span_days} days. Rule {beh.rule_version}.</p>
        </div>
      </div>
    </>
  );
}
