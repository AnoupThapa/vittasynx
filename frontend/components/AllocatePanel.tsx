"use client";

import { useState } from "react";
import { apiGet, apiSend } from "@/lib/api";
import { useOrg } from "@/components/OrgContext";
import { Badge, ErrorNotice, Money, useAction, useLoad } from "@/components/ui";
import { formatDate, isZero } from "@/lib/format";

/** Suggestions are shown for review; nothing is allocated until the user confirms each line. */
export function AllocatePanel({ source, kind, onDone }: { source: any; kind: "payment" | "credit_note"; onDone: () => void }) {
  const { base, can } = useOrg();
  const act = useAction();
  const [amounts, setAmounts] = useState<Record<string, string>>({});
  const [manualInvoice, setManualInvoice] = useState("");
  const [manualAmount, setManualAmount] = useState("");
  const open = useLoad(
    () => (source.customer_id ? apiGet(`${base}/invoices?customer_id=${source.customer_id}&status=outstanding`) : Promise.resolve({ items: [] })),
    [base, source.customer_id, source.unapplied],
  );
  if (!can("confirm_allocation") || isZero(source.unapplied)) return null;

  async function confirm(invoiceId: string, amount: string) {
    const body: any = { invoice_id: invoiceId, amount };
    body[kind === "payment" ? "payment_id" : "credit_note_id"] = source.id;
    if (await act.run(() => apiSend("POST", `${base}/allocations`, body))) {
      setAmounts({});
      setManualAmount("");
      onDone();
    }
  }

  return (
    <div className="panel">
      <h2>Allocate <Money value={source.unapplied} /> unapplied</h2>
      <ErrorNotice error={act.error} />
      {source.suggestions?.length > 0 ? (
        <>
          <p className="small muted">Suggested matches. Check each one; nothing is applied until you confirm.</p>
          <table><thead><tr><th>Invoice</th><th>Due</th><th className="num">Balance</th><th>Match</th><th className="num">Amount</th><th /></tr></thead>
            <tbody>{source.suggestions.map((s: any) => (
              <tr key={s.invoice_id}>
                <td>{s.invoice_number}<div className="small muted">{s.customer_name}</div></td><td>{formatDate(s.due_date)}</td>
                <td className="num"><Money value={s.invoice_balance} /></td>
                <td><Badge kind={s.confidence}>{s.confidence}</Badge><div className="small muted">{s.reason}</div></td>
                <td className="num"><input style={{ width: 110, textAlign: "right" }} value={amounts[s.invoice_id] ?? s.suggested_amount}
                  onChange={(e) => setAmounts({ ...amounts, [s.invoice_id]: e.target.value })} disabled={!source.customer_id} /></td>
                <td><button className="small primary" disabled={act.busy || !source.customer_id}
                  onClick={() => confirm(s.invoice_id, amounts[s.invoice_id] ?? s.suggested_amount)}>Confirm</button></td>
              </tr>))}</tbody></table>
          {!source.customer_id && <p className="small" style={{ color: "var(--warn)", marginTop: 8 }}>Assign this receipt to a customer before allocating.</p>}
        </>
      ) : <p className="small muted">No suggested matches.</p>}
      {source.customer_id && (open.data?.items?.length ?? 0) > 0 && (
        <div className="inline" style={{ marginTop: 14 }}>
          <div className="field"><label htmlFor="mi">Or choose an invoice</label>
            <select id="mi" value={manualInvoice} onChange={(e) => setManualInvoice(e.target.value)}>
              <option value="">Select…</option>
              {open.data.items.map((i: any) => <option key={i.id} value={i.id}>{i.invoice_number} · balance {i.balance}</option>)}
            </select></div>
          <div className="field"><label htmlFor="ma">Amount</label><input id="ma" style={{ width: 120 }} value={manualAmount} onChange={(e) => setManualAmount(e.target.value)} placeholder="0.00" /></div>
          <button disabled={!manualInvoice || !manualAmount || act.busy} onClick={() => confirm(manualInvoice, manualAmount)}>Confirm allocation</button>
        </div>
      )}
    </div>
  );
}
