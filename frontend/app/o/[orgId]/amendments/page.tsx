"use client";

import Link from "next/link";
import { apiGet, apiSend } from "@/lib/api";
import { useOrg } from "@/components/OrgContext";
import { Empty, ErrorNotice, Loading, useAction, useLoad } from "@/components/ui";

export default function Amendments() {
  const { base, org, can } = useOrg();
  const { data, error, reload } = useLoad(() => apiGet(`${base}/amendments`), [base]);
  const act = useAction();
  async function review(id: string, approve: boolean) {
    const reason = window.prompt(approve ? "Note for the audit log (optional)" : "Why is this change rejected?") ?? undefined;
    if (!approve && !reason) return;
    if (await act.run(() => apiSend("POST", `${base}/amendments/${id}/${approve ? "approve" : "reject"}`, { reason }))) reload();
  }
  return (
    <>
      <div className="page-head"><div><h1>Amendments</h1><div className="sub">Re-imported invoices whose values changed. Nothing changes until approved.</div></div></div>
      <ErrorNotice error={error || act.error} />
      <div className="panel flush">
        {!data ? <Loading /> : data.items.length === 0 ? <Empty>No pending amendments.</Empty> : (
          <table><thead><tr><th>Invoice</th><th>Changes</th><th>Source line</th>{can("approve_amendment") && <th />}</tr></thead>
            <tbody>{data.items.map((a: any) => (
              <tr key={a.id}><td><Link href={`/o/${org.id}/invoices/${a.invoice_id}`}>{a.invoice_number}</Link></td>
                <td className="small">{Object.entries(a.changes).map(([k, v]: any) => <div key={k}><span className="muted">{k.replace(/_/g, " ")}:</span> {v.from ?? "—"} → <strong>{v.to ?? "—"}</strong></div>)}</td>
                <td className="num">{a.row_number}</td>
                {can("approve_amendment") && <td><div className="toolbar"><button className="small primary" disabled={act.busy} onClick={() => review(a.id, true)}>Approve</button>
                  <button className="small" disabled={act.busy} onClick={() => review(a.id, false)}>Reject</button></div></td>}</tr>))}</tbody></table>
        )}
      </div>
      <p className="def">Approving creates a new invoice version; the previous version and the source rows are kept. An amount below confirmed allocations is blocked until those allocations are reversed.</p>
    </>
  );
}
