"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { apiSend } from "@/lib/api";
import { AuthCard, ErrorNotice, useAction } from "@/components/ui";

function MfaForm() {
  const router = useRouter();
  const next = useSearchParams().get("next");
  const [code, setCode] = useState("");
  const { busy, error, run } = useAction();
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (await run(() => apiSend("POST", "/auth/mfa/verify", { code }))) {
      router.push(next && next.startsWith("/") && !next.startsWith("//") ? next : "/");
    }
  }
  return (
    <AuthCard title="Two-factor authentication">
      <p className="muted">Enter the 6-digit code from your authenticator app, or one of your recovery codes if you've lost your phone.</p>
      <ErrorNotice error={error} />
      <form onSubmit={submit}>
        <div className="field"><label htmlFor="code">Code</label>
          <input id="code" autoComplete="one-time-code" maxLength={12} required
            value={code} onChange={(e) => setCode(e.target.value.trim())} /></div>
        <button className="primary" disabled={busy} style={{ width: "100%", justifyContent: "center" }}>Verify</button>
      </form>
    </AuthCard>
  );
}

export default function Page() {
  return <Suspense><MfaForm /></Suspense>;
}
