"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { apiGet } from "@/lib/api";
import { useOrg } from "@/components/OrgContext";
import { AllocatePanel } from "@/components/AllocatePanel";
import { AllocationTable } from "@/components/AllocationTable";
import { ErrorNotice, Loading, Money, useLoad } from "@/components/ui";
import { formatDate } from "@/lib/format";

export default function CreditNoteDetail() {
  const { creditNoteId } = useParams<{ creditNoteId: string }>();
  const { base, org } = useOrg();
  const { data: c, error, reload } = useLoad(() => apiGet(`${base}/credit-notes/${creditNoteId}`), [base, creditNoteId]);
  if (error) return <ErrorNotice error={error} />;
  if (!c) return <Loading />;
  return (
    <>
      <div className="page-head"><div>
        <div className="small"><Link href={`/o/${org.id}/credit-notes`}>Credit notes</Link> /</div>
        <h1>Credit note {c.credit_note_number}</h1>
        <div className="sub">{c.customer_name} · {formatDate(c.credit_date)}{c.reason ? ` · ${c.reason}` : ""}{c.applies_to_invoice ? ` · for ${c.applies_to_invoice}` : ""}</div></div></div>
      <div className="figures">
        <div className="figure"><div className="label">Amount</div><div className="value"><Money value={c.amount} /></div></div>
        <div className="figure"><div className="label">Allocated</div><div className="value"><Money value={c.allocated} /></div></div>
        <div className="figure"><div className="label">Unapplied</div><div className="value"><Money value={c.unapplied} /></div></div>
      </div>
      <AllocatePanel source={c} kind="credit_note" onDone={reload} />
      <AllocationTable allocations={c.allocations} onChange={reload} />
    </>
  );
}
