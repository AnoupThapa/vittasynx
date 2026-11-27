"use client";

import { useState } from "react";
import { apiGet } from "@/lib/api";
import { useOrg } from "@/components/OrgContext";
import { ErrorNotice, Loading, useLoad } from "@/components/ui";
import { formatDateTime } from "@/lib/format";

export default function Audit() {
  const { base } = useOrg();
  const [type, setType] = useState("");
  const { data, error } = useLoad(() => apiGet(`${base}/audit?limit=200${type ? `&entity_type=${type}` : ""}`), [base, type]);
  return (
    <>
      <div className="page-head"><div><h1>Audit log</h1><div className="sub">Every import, edit, allocation, membership and settings change. Entries cannot be edited or deleted.</div></div>
        <select value={type} onChange={(e) => setType(e.target.value)} aria-label="Filter" style={{ width: "auto" }}>
          <option value="">All</option>{["invoice", "allocation", "payment", "credit_note", "customer", "import_batch", "membership", "invitation", "organisation", "report"].map((t) => <option key={t} value={t}>{t.replace("_", " ")}</option>)}</select></div>
      <ErrorNotice error={error} />
      <div className="panel flush">
        {!data ? <Loading /> : (
          <div className="table-wrap"><table><thead><tr><th>When</th><th>Who</th><th>Action</th><th>Details</th></tr></thead>
            <tbody>{data.items.map((e: any) => (
              <tr key={e.id}><td className="small" style={{ whiteSpace: "nowrap" }}>{formatDateTime(e.at)}</td><td>{e.actor ?? "—"}</td><td><code className="small">{e.action}</code></td>
                <td className="small mono" style={{ maxWidth: 520, overflowWrap: "anywhere" }}>{e.after ? JSON.stringify(e.after) : ""}{e.note ? ` · ${e.note}` : ""}</td></tr>))}</tbody></table></div>
        )}
      </div>
    </>
  );
}
