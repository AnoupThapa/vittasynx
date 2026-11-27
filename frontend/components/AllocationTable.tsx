"use client";

import Link from "next/link";
import { apiSend } from "@/lib/api";
import { useOrg } from "@/components/OrgContext";
import { Badge, ErrorNotice, Money, useAction } from "@/components/ui";
import { formatDate } from "@/lib/format";

export function AllocationTable({ allocations, onChange }: { allocations: any[]; onChange: () => void }) {
  const { base, org, can } = useOrg();
  const act = useAction();
  return (
    <div className="panel flush">
      <div className="panel-head"><h2>Allocations</h2></div>
      <ErrorNotice error={act.error} />
      {allocations.length === 0 ? <div className="empty">Not allocated to any invoice yet.</div> : (
        <table><thead><tr><th>Invoice</th><th>Effective</th><th className="num">Amount</th><th>Status</th><th /></tr></thead>
          <tbody>{allocations.map((a) => (
            <tr key={a.id}><td><Link href={`/o/${org.id}/invoices/${a.invoice_id}`}>View invoice</Link></td><td>{formatDate(a.effective_date)}</td>
              <td className="num"><Money value={a.amount} /></td>
              <td><Badge kind={a.status === "reversed" ? "reversed" : "paid"}>{a.status}</Badge>{a.reversal_reason && <div className="small muted">{a.reversal_reason}</div>}</td>
              <td>{a.status === "confirmed" && can("reverse_allocation") && (
                <button className="small danger" disabled={act.busy} onClick={async () => {
                  const why = window.prompt("Reason for reversing this allocation?");
                  if (why && await act.run(() => apiSend("POST", `${base}/allocations/${a.id}/reverse`, { reason: why }))) onChange();
                }}>Reverse</button>)}</td></tr>))}</tbody></table>
      )}
    </div>
  );
}
