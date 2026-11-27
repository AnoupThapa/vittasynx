"use client";

import { useOrg } from "@/components/OrgContext";

/** Every receivables figure is calculated as at an explicit reporting date. */
export function ReportingDate({ shown }: { shown?: string }) {
  const { asAt, setAsAt, org } = useOrg();
  return (
    <div className="inline">
      <div className="field">
        <label htmlFor="as-at">Reporting date</label>
        <input id="as-at" type="date" value={asAt || shown || ""} onChange={(e) => setAsAt(e.target.value)} />
      </div>
      {asAt && <button className="small" onClick={() => setAsAt("")}>Today</button>}
      <span className="muted small" style={{ paddingBottom: 8 }}>{org.timezone}</span>
    </div>
  );
}
