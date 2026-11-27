"use client";

import Link from "next/link";
import { useState } from "react";
import { apiSend } from "@/lib/api";
import { AuthCard, ErrorNotice, Notice, useAction } from "@/components/ui";

export default function Register() {
  const [form, setForm] = useState({ full_name: "", email: "", password: "" });
  const [done, setDone] = useState(false);
  const { busy, error, run } = useAction();

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (await run(() => apiSend("POST", "/auth/register", form))) setDone(true);
  }

  if (done) {
    return (
      <AuthCard title="Check your email">
        <Notice kind="ok">Account created. We sent a verification link to {form.email}.</Notice>
        <p className="muted small">You can sign in now. Verify your email before accepting invitations to an organisation.</p>
        <Link className="btn primary" href="/login">Continue to sign in</Link>
      </AuthCard>
    );
  }
  return (
    <AuthCard title="Create your account">
      <ErrorNotice error={error} />
      <form onSubmit={submit}>
        <div className="field"><label htmlFor="name">Full name</label>
          <input id="name" required value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} /></div>
        <div className="field"><label htmlFor="email">Work email</label>
          <input id="email" type="email" autoComplete="username" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></div>
        <div className="field"><label htmlFor="pw">Password</label>
          <input id="pw" type="password" autoComplete="new-password" minLength={12} required value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
          <div className="def">At least 12 characters. A short phrase works well.</div></div>
        <button className="primary" disabled={busy} style={{ width: "100%", justifyContent: "center" }}>Create account</button>
      </form>
      <div className="foot">Already registered? <Link href="/login">Sign in</Link></div>
    </AuthCard>
  );
}
