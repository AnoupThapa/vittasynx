"use client";

import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { apiGet, apiUpload } from "@/lib/api";
import { useOrg } from "@/components/OrgContext";
import { Badge, Empty, ErrorNotice, Loading, useAction, useLoad } from "@/components/ui";
import { formatDateTime } from "@/lib/format";

const KINDS: Record<string, string> = { invoices: "Invoices", credit_notes: "Credit notes", payments: "Customer payments", bank: "Bank transactions" };

export default function Imports() {
  const { base, org, can } = useOrg();
  const router = useRouter();
  const { data, error, loading } = useLoad(() => apiGet(`${base}/imports`), [base]);
  const [kind, setKind] = useState("invoices");
  const [file, setFile] = useState<File | null>(null);
  const act = useAction();

  async function upload(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    const form = new FormData();
    form.append("kind", kind);
    form.append("file", file);
    const batch = await act.run(() => apiUpload(`${base}/imports`, form));
    if (batch) router.push(`/o/${org.id}/imports/${batch.id}`);
  }

  return (
    <>
      <div className="page-head"><div><h1>Imports</h1><div className="sub">CSV or XLSX exports from your accounting system or bank</div></div></div>
      <div className="grid-3">
        <div>
          <ErrorNotice error={error} />
          <div className="panel flush">
            {loading && !data ? <Loading /> : !data?.items.length ? <Empty>No imports yet.</Empty> : (
              <table><thead><tr><th>File</th><th>Type</th><th>Uploaded</th><th>Status</th><th className="num">Rows</th></tr></thead>
                <tbody>{data.items.map((b: any) => (
                  <tr key={b.id}><td><Link href={`/o/${org.id}/imports/${b.id}`}>{b.filename}</Link></td><td>{KINDS[b.kind]}</td>
                    <td className="small">{formatDateTime(b.created_at)}</td>
                    <td><Badge kind={b.status === "committed" ? "committed" : b.status === "cancelled" ? "void" : "warn"}>{b.status}</Badge></td>
                    <td className="num">{b.summary?.total_rows ?? "—"}</td></tr>))}</tbody></table>
            )}
          </div>
        </div>
        {can("import") && (
          <div className="panel">
            <h2>New import</h2>
            <ErrorNotice error={act.error} />
            <form onSubmit={upload}>
              <div className="field"><label htmlFor="k">What does the file contain?</label>
                <select id="k" value={kind} onChange={(e) => setKind(e.target.value)}>{Object.entries(KINDS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></div>
              <div className="field"><label htmlFor="f">File (.csv or .xlsx, up to 5 MB)</label>
                <input id="f" type="file" accept=".csv,.xlsx" required onChange={(e) => setFile(e.target.files?.[0] ?? null)} /></div>
              <button className="primary" disabled={!file || act.busy}>{act.busy ? "Reading file…" : "Upload and preview"}</button>
            </form>
            <p className="def">Nothing is saved to your records until you review the rows and confirm. The original file is kept as source evidence.
              Templates: <code>docs/business-validation/templates/</code>.</p>
          </div>
        )}
      </div>
    </>
  );
}
