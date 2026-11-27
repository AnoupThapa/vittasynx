"use client";

import Link from "next/link";
import { apiGet, downloadUrl } from "@/lib/api";
import { asAtQuery, useOrg } from "@/components/OrgContext";
import { ReportingDate } from "@/components/ReportingDate";
import { Empty, ErrorNotice, Loading, Money, useLoad } from "@/components/ui";
import { BUCKET_LABELS, formatDate } from "@/lib/format";

const BUCKETS = ["current", "1_30", "31_60", "61_90", "91_plus"];

export default function Reports() {
  const { base, asAt, org, can } = useOrg();
  const { data, error } = useLoad(() => apiGet(`${base}/reports/customer-balances${asAtQuery(asAt)}`), [base, asAt]);
  const rows = (data?.items ?? []).filter((r: any) => r.total_outstanding !== "0.00" || r.unapplied_payments !== "0.00" || r.unapplied_credits !== "0.00");
  const q = asAtQuery(asAt);
  return (
    <>
      <div className="page-head">
        <div><h1>Ageing by customer</h1><div className="sub">{data ? `As at ${formatDate(data.reporting_date)} · ${org.currency}` : " "}</div></div>
        <div className="toolbar">
          <ReportingDate shown={data?.reporting_date} />
          {can("export") && <>
            <a className="btn" href={downloadUrl(`${base}/exports/ageing.csv${q}`)}>Ageing CSV</a>
            <a className="btn" href={downloadUrl(`${base}/exports/customer-balances.csv${q}`)}>Balances CSV</a>
            <a className="btn" href={downloadUrl(`${base}/exports/invoices.csv${q}`)}>Invoice register CSV</a></>}
        </div>
      </div>
      <ErrorNotice error={error} />
      <div className="panel flush">
        {!data ? <Loading /> : rows.length === 0 ? <Empty>Nothing outstanding.</Empty> : (
          <div className="table-wrap"><table>
            <thead><tr><th>Customer</th>{BUCKETS.map((b) => <th key={b} className="num">{BUCKET_LABELS[b]}</th>)}<th className="num">Total</th><th className="num">Unapplied</th></tr></thead>
            <tbody>{rows.map((r: any) => (
              <tr key={r.customer_id}><td><Link href={`/o/${org.id}/customers/${r.customer_id}`}>{r.customer_name}</Link></td>
                {BUCKETS.map((b) => <td key={b} className="num"><Money value={r[b]} /></td>)}
                <td className="num"><Money value={r.total_outstanding} strong /></td><td className="num"><Money value={r.unapplied_payments} /></td></tr>))}</tbody>
          </table></div>
        )}
      </div>
      <p className="def">Exports carry the organisation, reporting date, currency and rule version, and match these on-screen totals for the same date. Each export is recorded in the audit log.</p>
    </>
  );
}
