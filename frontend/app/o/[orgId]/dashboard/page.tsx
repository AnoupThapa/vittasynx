"use client";

import Link from "next/link";
import { apiGet } from "@/lib/api";
import { asAtQuery, useOrg } from "@/components/OrgContext";
import { ReportingDate } from "@/components/ReportingDate";
import { Empty, ErrorNotice, Loading, Money, Notice, useLoad } from "@/components/ui";
import { formatDate, formatDateTime, isZero } from "@/lib/format";

export default function Dashboard() {
  const { base, asAt, org } = useOrg();
  const { data: d, error, loading } = useLoad(() => apiGet(`${base}/dashboard${asAtQuery(asAt)}`), [base, asAt]);
  const link = (p: string) => `/o/${org.id}/${p}`;

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Receivables</h1>
          <div className="sub">{d ? <>As at <strong>{formatDate(d.reporting_date)}</strong> · {org.currency} · calculated {formatDateTime(d.generated_at)}</> : " "}</div>
        </div>
        <ReportingDate shown={d?.reporting_date} />
      </div>
      <ErrorNotice error={error} />
      {loading && !d && <Loading />}
      {d && (
        <>
          {!d.reconciles && <Notice kind="error">Ageing buckets do not reconcile to the outstanding total. Please report this.</Notice>}
          {d.totals.exception_count > 0 && (
            <Notice kind="warn">{d.totals.exception_count} invoice(s) have a negative balance and are excluded from ageing. <Link href={link("invoices?status=exception")}>Review</Link></Notice>
          )}
          <div className="figures">
            <div className="figure"><div className="label">Total outstanding</div><div className="value"><Money value={d.totals.total_outstanding} /></div>
              <div className="note">{d.totals.open_invoice_count} open invoices</div></div>
            <div className={`figure ${isZero(d.totals.overdue_total) ? "" : "alert"}`}><div className="label">Overdue</div>
              <div className="value"><Money value={d.totals.overdue_total} /></div><div className="note">{d.totals.overdue_count} invoices past due</div></div>
            <div className="figure"><div className="label">Current (not yet due)</div><div className="value"><Money value={d.totals.current_total} /></div></div>
            <div className="figure"><div className="label">Unapplied payments</div><div className="value"><Money value={d.totals.unapplied_payments} /></div>
              <div className="note">{d.totals.unapplied_payment_count} receipts · not deducted</div></div>
            <div className="figure"><div className="label">Unapplied credits</div><div className="value"><Money value={d.totals.unapplied_credits} /></div></div>
          </div>

          <div className="panel">
            <div className="panel-head"><h2>Ageing</h2><Link href={link("reports")} className="small">Ageing by customer →</Link></div>
            <AgeingBar ageing={d.ageing} total={d.totals.total_outstanding} />
            <div className="table-wrap"><table>
              <thead><tr><th>Bucket</th><th className="num">Invoices</th><th className="num">Outstanding</th></tr></thead>
              <tbody>{d.ageing.map((a: any) => (
                <tr key={a.bucket}><td><span className={`swatch b-${a.bucket}`} />{a.label}</td><td className="num">{a.count}</td><td className="num"><Money value={a.total} /></td></tr>
              ))}</tbody>
              <tfoot><tr><td>Total</td><td className="num">{d.totals.open_invoice_count}</td><td className="num"><Money value={d.totals.total_outstanding} /></td></tr></tfoot>
            </table></div>
          </div>

          <div className="grid-2">
            <div className="panel flush">
              <div className="panel-head"><h2>Largest overdue customers</h2></div>
              {d.largest_overdue_customers.length === 0 ? <Empty>No overdue customers.</Empty> : (
                <table><thead><tr><th>Customer</th><th className="num">Overdue</th><th className="num">Total owed</th></tr></thead>
                  <tbody>{d.largest_overdue_customers.map((c: any) => (
                    <tr key={c.customer_id}><td><Link href={link(`customers/${c.customer_id}`)}>{c.customer_name}</Link></td>
                      <td className="num"><Money value={c.overdue} /></td><td className="num"><Money value={c.outstanding} /></td></tr>))}</tbody></table>
              )}
            </div>
            <div className="panel flush">
              <div className="panel-head"><h2>Oldest outstanding invoices</h2><Link className="small" href={link("invoices?status=overdue")}>All overdue →</Link></div>
              {d.oldest_outstanding_invoices.length === 0 ? <Empty>Nothing outstanding.</Empty> : (
                <table><thead><tr><th>Invoice</th><th>Customer</th><th className="num">Days late</th><th className="num">Balance</th></tr></thead>
                  <tbody>{d.oldest_outstanding_invoices.map((i: any) => (
                    <tr key={i.invoice_id}><td><Link href={link(`invoices/${i.invoice_id}`)}>{i.invoice_number}</Link></td><td>{i.customer_name}</td>
                      <td className="num">{i.days_past_due}</td><td className="num"><Money value={i.balance} /></td></tr>))}</tbody></table>
              )}
            </div>
            <div className="panel flush">
              <div className="panel-head"><h2>Recent payments</h2><Link className="small" href={link("payments")}>All payments →</Link></div>
              {d.recent_payments.length === 0 ? <Empty>No payments recorded.</Empty> : (
                <table><thead><tr><th>Date</th><th>Customer</th><th>Reference</th><th className="num">Amount</th></tr></thead>
                  <tbody>{d.recent_payments.map((p: any) => (
                    <tr key={p.payment_id}><td>{formatDate(p.payment_date)}</td><td>{p.customer_name ?? <span className="badge warn">Unassigned</span>}</td>
                      <td className="small">{p.reference ?? "—"}</td><td className="num"><Link href={link(`payments/${p.payment_id}`)}><Money value={p.amount} /></Link></td></tr>))}</tbody></table>
              )}
            </div>
            <div className="panel flush">
              <div className="panel-head"><h2>Unapplied payments</h2><Link className="small" href={link("payments?unapplied=1")}>Allocate →</Link></div>
              {d.unapplied_payments.length === 0 ? <Empty>All payments are allocated.</Empty> : (
                <table><thead><tr><th>Date</th><th>Customer</th><th className="num">Unapplied</th></tr></thead>
                  <tbody>{d.unapplied_payments.map((p: any) => (
                    <tr key={p.payment_id}><td>{formatDate(p.payment_date)}</td><td>{p.customer_name ?? <span className="badge warn">Unassigned</span>}</td>
                      <td className="num"><Link href={link(`payments/${p.payment_id}`)}><Money value={p.unapplied} /></Link></td></tr>))}</tbody></table>
              )}
            </div>
          </div>

          <details className="defs">
            <summary>How these figures are calculated (rule version {d.rule_version})</summary>
            <dl>{Object.entries(d.definitions).map(([k, v]) => (<div key={k}><dt>{k.replace(/_/g, " ")}</dt><dd>{v as string}</dd></div>))}</dl>
          </details>
        </>
      )}
    </>
  );
}

function AgeingBar({ ageing, total }: { ageing: any[]; total: string }) {
  if (isZero(total)) return <div className="ageing-bar" />;
  // Proportions are for display only, computed from exact strings via integer cents.
  const cents = (s: string) => BigInt(s.replace(".", ""));
  const t = cents(total);
  return (
    <div className="ageing-bar" aria-hidden>
      {ageing.map((a) => {
        const pct = Number((cents(a.total) * 10000n) / t) / 100;
        return pct > 0 ? <span key={a.bucket} className={`b-${a.bucket}`} style={{ width: `${pct}%` }} title={`${a.label}: ${a.total}`} /> : null;
      })}
    </div>
  );
}
