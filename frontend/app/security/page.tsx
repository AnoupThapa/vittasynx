"use client";

import Link from "next/link";
import { useState } from "react";
import { apiGet, apiSend } from "@/lib/api";
import { AuthCard, ErrorNotice, Loading, Notice, useAction, useLoad } from "@/components/ui";

export default function Security() {
  const me = useLoad(() => apiGet("/auth/me"), []);
  const [setup, setSetup] = useState<{ secret: string; otpauth_uri: string } | null>(null);
  const [code, setCode] = useState("");
  const [enabled, setEnabled] = useState(false);
  const { busy, error, run } = useAction();

  if (!me.data) return <Loading />;
  const already = me.data.user.mfa_enabled || enabled;
  return (
    <AuthCard title="Two-factor authentication">
      <ErrorNotice error={error} />
      {already ? (
        <Notice kind="ok">Two-factor authentication is on for {me.data.user.email}.</Notice>
      ) : !setup ? (
        <>
          <p className="muted">Protect your account with an authenticator app (Google Authenticator, Microsoft Authenticator, 1Password and similar).
            It is required for Owners and Administrators.</p>
          <button className="primary" disabled={busy} onClick={async () => { const r = await run(() => apiSend("POST", "/auth/mfa/setup")); if (r) setSetup(r); }}>Start setup</button>
        </>
      ) : (
        <form onSubmit={async (e) => { e.preventDefault(); if (await run(() => apiSend("POST", "/auth/mfa/enable", { code }))) setEnabled(true); }}>
          <p>1. In your authenticator app, add an account using this setup key:</p>
          <p className="mono" style={{ wordBreak: "break-all", background: "var(--bg)", padding: 8, borderRadius: 6 }}>{setup.secret}</p>
          <p className="small"><a href={setup.otpauth_uri}>Open in an authenticator app on this device</a></p>
          <div className="field"><label htmlFor="code">2. Enter the 6-digit code it shows</label>
            <input id="code" inputMode="numeric" maxLength={6} required value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} /></div>
          <button className="primary" disabled={busy}>Turn on</button>
        </form>
      )}
      <div className="foot"><Link href="/">Back to Vittasynx</Link></div>
    </AuthCard>
  );
}
