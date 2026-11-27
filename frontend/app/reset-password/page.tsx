"use client";

import Link from "next/link";
import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { apiSend } from "@/lib/api";
import { AuthCard, ErrorNotice, Notice, useAction } from "@/components/ui";

function ResetForm() {
  const token = useSearchParams().get("token") || "";
  const [pw, setPw] = useState("");
  const [done, setDone] = useState(false);
  const { busy, error, run } = useAction();
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (await run(() => apiSend("POST", "/auth/password-reset/confirm", { token, new_password: pw }))) setDone(true);
  }
  return (
    <AuthCard title="Choose a new password">
      {done ? <><Notice kind="ok">Password updated. All other sessions were signed out.</Notice><Link className="btn primary" href="/login">Sign in</Link></> : (
        <>
          <ErrorNotice error={error} />
          <form onSubmit={submit}>
            <div className="field"><label htmlFor="pw">New password</label>
              <input id="pw" type="password" autoComplete="new-password" minLength={12} required value={pw} onChange={(e) => setPw(e.target.value)} /></div>
            <button className="primary" disabled={busy || !token}>Update password</button>
          </form>
        </>
      )}
    </AuthCard>
  );
}

export default function Page() {
  return <Suspense><ResetForm /></Suspense>;
}
