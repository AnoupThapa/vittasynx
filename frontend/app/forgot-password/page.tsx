"use client";

import Link from "next/link";
import { useState } from "react";
import { apiSend } from "@/lib/api";
import { AuthCard, ErrorNotice, Notice, useAction } from "@/components/ui";

export default function Forgot() {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const { busy, error, run } = useAction();
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const r = await run(() => apiSend("POST", "/auth/password-reset/request", { email }));
    if (r) setMessage(r.message);
  }
  return (
    <AuthCard title="Reset your password">
      {message ? <Notice kind="ok">{message}</Notice> : (
        <>
          <ErrorNotice error={error} />
          <form onSubmit={submit}>
            <div className="field"><label htmlFor="email">Email</label>
              <input id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} /></div>
            <button className="primary" disabled={busy}>Send reset link</button>
          </form>
        </>
      )}
      <div className="foot"><Link href="/login">Back to sign in</Link></div>
    </AuthCard>
  );
}
