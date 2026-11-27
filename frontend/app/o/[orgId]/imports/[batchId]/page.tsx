"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { apiGet, apiSend, downloadUrl, ApiError } from "@/lib/api";
import { useOrg } from "@/components/OrgContext";
import { Badge, ErrorNotice, Loading, Notice, useAction, useLoad } from "@/components/ui";
import { ROW_STATUS_LABELS } from "@/lib/format";

const DATE_FORMATS = ["DD/MM/YYYY", "YYYY-MM-DD", "MM/DD/YYYY", "DD-MM-YYYY", "DD.MM.YYYY"];

export default function ImportBatch() {
  const { batchId } = useParams<{ batchId: string }>();
  const { base, org, can } = useOrg();
  const batch = useLoad(() => apiGet(`${base}/imports/${batchId}`), [base, batchId]);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [dateFormat, setDateFormat] = useState("DD/MM/YYYY");
  const [filter, setFilter] = useState("");
  const rows = useLoad(() => apiGet(`${base}/imports/${batchId}/rows${filter ? `?status=${filter}` : ""}`), [base, batchId, filter, batch.data?.summary]);
  const act = useAction();
  const [confirmCustomers, setConfirmCustomers] = useState(false);
  const [excludeErrors, setExcludeErrors] = useState(false);
  const [newCustomers, setNewCustomers] = useState<any[] | null>(null);

  useEffect(() => {
    if (batch.data) {
      setMapping(batch.data.mapping || {});
      setDateFormat(batch.data.options?.date_format || "DD/MM/YYYY");
      setNewCustomers(batch.data.summary?.new_customers ?? null);
    }
  }, [batch.data?.id, batch.data?.status]);

  if (batch.error) return <ErrorNotice error={batch.error} />;
  const b = batch.data;
  if (!b) return <Loading />;
  const editable = can("import") && (b.status === "uploaded" || b.status === "validated");
  const counts: Record<string, number> = b.summary?.by_status ?? {};
  const step = b.status === "uploaded" ? 1 : b.status === "validated" ? 2 : 3;

  async function validate() {
    const r = await act.run(() => apiSend("POST", `${base}/imports/${batchId}/validate`, { mapping, date_format: dateFormat }));
    if (r) batch.setData({ ...r, preview: b!.preview });
  }
  async function rowAction(rowId: string, action: string, corrections?: Record<string, string>) {
    const r = await act.run(() => apiSend("PATCH", `${base}/imports/${batchId}/rows/${rowId}`, { action, corrections }));
    if (r) batch.setData({ ...r, preview: b!.preview });
  }
  async function commit() {
    const r = await act.run(() => apiSend("POST", `${base}/imports/${batchId}/commit`, { confirm_new_customers: confirmCustomers, exclude_errors: excludeErrors }));
    if (r) batch.setData({ ...r, preview: b!.preview });
  }
  const err = act.error as ApiError | null;

  return (
    <>
      <div className="page-head"><div>
        <div className="small"><Link href={`/o/${org.id}/imports`}>Imports</Link> /</div>
        <h1>{b.filename}</h1>
        <div className="sub">{b.kind.replace("_", " ")} · {b.summary?.total_rows ?? b.preview?.length} rows · <a href={downloadUrl(`${base}/imports/${batchId}/file`)}>original file</a></div></div>
        {editable && <button className="danger" onClick={async () => { const r = await act.run(() => apiSend("POST", `${base}/imports/${batchId}/cancel`)); if (r) batch.setData(r); }}>Cancel import</button>}
      </div>
      <div className="steps"><span className={step > 1 ? "done" : "on"}>1 · Map columns</span><span className={step > 2 ? "done" : step === 2 ? "on" : ""}>2 · Review rows</span><span className={step === 3 ? "done" : ""}>3 · Imported</span></div>
      {b.warnings?.map((w: any) => <Notice key={w.code} kind="warn">{w.message}</Notice>)}
      {b.status === "cancelled" && <Notice kind="info">This import was cancelled. Nothing was saved.</Notice>}
      {b.status === "committed" && b.summary?.result && (
        <Notice kind="ok">Import complete: {Object.entries(b.summary.result).map(([k, v]) => `${v} ${(ROW_STATUS_LABELS[k] ?? k).toLowerCase()}`).join(", ")}.
          {b.summary.customers_created ? ` ${b.summary.customers_created} new customer(s) created.` : ""}
          {b.summary.result.amendment_pending ? <> <Link href={`/o/${org.id}/amendments`}>Review amendments</Link>.</> : null}</Notice>
      )}
      <ErrorNotice error={act.error} />

      {editable && (
        <div className="panel">
          <h2>Column mapping</h2>
          <p className="small muted">Match each Vittasynx field to a column in your file. Suggestions are based on column names; check them.</p>
          <div className="table-wrap"><table>
            <thead><tr><th>Vittasynx field</th><th>Column in your file</th><th>Example value</th></tr></thead>
            <tbody>{b.fields.map((f: any) => (
              <tr key={f.key}><td>{f.label}{f.required && <span style={{ color: "var(--danger)" }}> *</span>}</td>
                <td><select value={mapping[f.key] ?? ""} onChange={(e) => setMapping({ ...mapping, [f.key]: e.target.value })}>
                  <option value="">— not in file —</option>{b.headers.map((h: string) => <option key={h} value={h}>{h}</option>)}</select></td>
                <td className="small mono">{mapping[f.key] ? b.preview?.[0]?.values?.[mapping[f.key]] ?? "" : ""}</td></tr>))}</tbody>
          </table></div>
          <div className="inline" style={{ marginTop: 12 }}>
            <div className="field"><label htmlFor="df">Date format in this file</label>
              <select id="df" value={dateFormat} onChange={(e) => setDateFormat(e.target.value)}>{DATE_FORMATS.map((d) => <option key={d}>{d}</option>)}</select></div>
            <button className="primary" disabled={act.busy} onClick={validate}>{b.status === "validated" ? "Re-validate" : "Validate rows"}</button>
          </div>
          {b.status === "validated" && <p className="def">Re-validating with a new mapping clears row corrections and exclusions.</p>}
        </div>
      )}

      {b.status !== "uploaded" && (
        <div className="panel flush">
          <div className="panel-head"><h2>Rows</h2>
            <div className="toolbar small">
              <button className={`small ${filter === "" ? "primary" : ""}`} onClick={() => setFilter("")}>All</button>
              {Object.entries(counts).map(([k, v]) => (
                <button key={k} className={`small ${filter === k ? "primary" : ""}`} onClick={() => setFilter(k)}>{ROW_STATUS_LABELS[k] ?? k} ({v})</button>))}
            </div></div>
          {!rows.data ? <Loading /> : (
            <div className="table-wrap"><table>
              <thead><tr><th>Line</th><th>Status</th><th>Values</th><th>Messages</th>{b.status === "validated" && <th />}</tr></thead>
              <tbody>{rows.data.items.map((r: any) => (
                <tr key={r.id}>
                  <td className="num">{r.row_number}</td>
                  <td><Badge kind={r.status}>{ROW_STATUS_LABELS[r.status] ?? r.status}</Badge></td>
                  <td className="small">{b.fields.filter((f: any) => mapping[f.key]).map((f: any) => [f.key, mapping[f.key]] as [string, string]).map(([k, h]: [string, string]) => (
                    <div key={k}><span className="muted">{k.replace(/_/g, " ")}:</span> {r.corrections?.[k] !== undefined ? <><s className="muted">{r.raw[h]}</s> <strong>{r.corrections[k]}</strong></> : r.raw[h] || <span className="muted">(blank)</span>}</div>))}</td>
                  <td className="small">{r.messages.map((m: any, i: number) => <div key={i}>{m.message}</div>)}</td>
                  {b.status === "validated" && (
                    <td><div className="toolbar">
                      {r.status !== "excluded" && <button className="small" onClick={() => rowAction(r.id, "exclude")}>Exclude</button>}
                      {(r.status === "excluded" || r.status === "needs_review") && <button className="small" onClick={() => rowAction(r.id, r.status === "excluded" ? "reset" : "include")}>{r.status === "excluded" ? "Restore" : "Include"}</button>}
                      {r.status === "error" && r.messages[0]?.field && (
                        <button className="small" onClick={() => {
                          const field = r.messages[0].field;
                          const v = window.prompt(`Corrected value for ${field.replace(/_/g, " ")} (the original stays on record):`, r.raw[mapping[field]] ?? "");
                          if (v !== null) rowAction(r.id, "correct", { [field]: v });
                        }}>Correct</button>)}
                    </div></td>)}
                </tr>))}</tbody>
            </table></div>
          )}
        </div>
      )}

      {b.status === "validated" && can("import") && (
        <div className="panel">
          <h2>Confirm import</h2>
          {(newCustomers?.length ?? 0) > 0 && (
            <div className="field">
              <Notice kind="info">{newCustomers!.length} customer(s) are not in Vittasynx yet: {newCustomers!.slice(0, 8).map((c) => c.name).join(", ")}{newCustomers!.length > 8 ? "…" : ""}</Notice>
              <label><input type="checkbox" style={{ width: "auto", marginRight: 6 }} checked={confirmCustomers} onChange={(e) => setConfirmCustomers(e.target.checked)} />Create these customers</label>
            </div>
          )}
          {(counts.error ?? 0) > 0 && (
            <div className="field"><label><input type="checkbox" style={{ width: "auto", marginRight: 6 }} checked={excludeErrors} onChange={(e) => setExcludeErrors(e.target.checked)} />
              Exclude the {counts.error} row(s) with errors and import the rest</label></div>
          )}
          {err?.code === "rows_need_review" && <Notice kind="warn">Include or exclude every row marked "Needs review" first.</Notice>}
          <button className="primary" disabled={act.busy} onClick={commit}>Import {counts.valid ?? 0} new record(s)</button>
          <p className="def">{counts.duplicate ?? 0} already-imported row(s) will be skipped. {counts.amendment ?? 0} changed invoice(s) will wait for a Finance Manager's approval; existing values are not overwritten.</p>
        </div>
      )}
    </>
  );
}
