"use client";

import Link from "next/link";
import { useState } from "react";
import { useParams } from "next/navigation";
import { apiGet, apiSend } from "@/lib/api";
import { useOrg } from "@/components/OrgContext";
import { AllocatePanel } from "@/components/AllocatePanel";
import { AllocationTable } from "@/components/AllocationTable";
import { Badge, ErrorNotice, Loading, Money, useAction, useLoad } from "@/components/ui";
import { formatDate } from "@/lib/format";

export default function PaymentDetail() {
  const { paymentId } = useParams<{ paymentId: string }>();
  const { base, org, can } = useOrg();
  const { data: p, error, reload } = useLoad(() => apiGet(`${base}/payments/${paymentId}`), [base, paymentId]);
  const customers = useLoad(() => apiGet(`${base}/customers`), [base]);
  const [assignTo, setAssignTo] = useState("");
  const act = useAction();
  if (error) return <ErrorNotice error={error} />;
  if (!p) return <Loading />;
  return (
    <>
      <div className="page-head"><div>
        <div className="small"><Link href={`/o/${org.id}/payments`}>Payments</Link> /</div>
        <h1>Payment of <Money value={p.amount} /> {!p.assigned && <Badge kind="warn">Unassigned</Badge>}</h1>
        <div className="sub">{formatDate(p.payment_date)} · {p.customer_name ?? "No customer"} · {p.source}</div></div></div>
      <div className="figures">
        <div className="figure"><div className="label">Amount</div><div className="value"><Money value={p.amount} /></div></div>
        <div className="figure"><div className="label">Allocated</div><div className="value"><Money value={p.allocated} /></div></div>
        <div className="figure"><div className="label">Unapplied</div><div className="value"><Money value={p.unapplied} /></div></div>
      </div>
      <div className="grid-3">
        <div>
          <AllocatePanel source={p} kind="payment" onDone={reload} />
          <AllocationTable allocations={p.allocations} onChange={reload} />
        </div>
        <div className="panel">
          <h2>Details</h2>
          <dl className="kv"><dt>Reference</dt><dd>{p.reference ?? "—"}</dd><dt>Bank description</dt><dd>{p.description ?? "—"}</dd><dt>Method</dt><dd>{p.method ?? "—"}</dd></dl>
          {can("record_payment") && (
            <div style={{ marginTop: 16 }}>
              <h3>{p.assigned ? "Change customer" : "Assign to a customer"}</h3>
              <ErrorNotice error={act.error} />
              <div className="inline">
                <select value={assignTo} onChange={(e) => setAssignTo(e.target.value)} aria-label="Customer">
                  <option value="">Select…</option>{customers.data?.items.map((c: any) => <option key={c.id} value={c.id}>{c.name}</option>)}</select>
                <button disabled={!assignTo || act.busy} onClick={async () => { if (await act.run(() => apiSend("POST", `${base}/payments/${paymentId}/assign-customer`, { customer_id: assignTo }))) reload(); }}>Assign</button>
              </div>
              <p className="def">A payment's customer can only change while nothing is allocated.</p>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
