"use client";

import { useState } from "react";
import { apiSend } from "@/lib/api";
import { useOrg } from "@/components/OrgContext";
import { ErrorNotice, Notice, useAction } from "@/components/ui";

export default function Settings() {
  const { base, org, can } = useOrg();
  const [form, setForm] = useState({ name: org.name, timezone: org.timezone });
  const [saved, setSaved] = useState(false);
  const act = useAction();
  return (
    <>
      <div className="page-head"><div><h1>Settings</h1></div></div>
      <div className="panel" style={{ maxWidth: 560 }}>
        <ErrorNotice error={act.error} />
        {saved && <Notice kind="ok">Saved. Reload the page to see the new name everywhere.</Notice>}
        <div className="field"><label htmlFor="n">Organisation name</label><input id="n" disabled={!can("manage_settings")} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
        <div className="field"><label htmlFor="t">Timezone (IANA name)</label><input id="t" disabled={!can("manage_settings")} value={form.timezone} onChange={(e) => setForm({ ...form, timezone: e.target.value })} />
          <div className="def">Decides which day is "today" for ageing.</div></div>
        <div className="field"><label>Reporting currency</label><input disabled value={org.currency} /><div className="def">Fixed when the organisation was created.</div></div>
        {can("manage_settings") && <button className="primary" disabled={act.busy} onClick={async () => { if (await act.run(() => apiSend("PATCH", base, form))) setSaved(true); }}>Save</button>}
      </div>
    </>
  );
}
