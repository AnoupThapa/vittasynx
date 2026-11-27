"use client";

import Link from "next/link";
import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { apiSend } from "@/lib/api";
import { AuthCard, ErrorNotice, useAction } from "@/components/ui";

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const { busy, error, run } = useAction();
  const next = params.get("next");
  const safeNext = next && next.startsWith("/") && !next.startsWith("//") ? next : "/";

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const res = await run(() => apiSend("POST", "/auth/login", { email, password }));
    if (res) router.push(res.mfa_required ? `/mfa?next=${encodeURIComponent(safeNext)}` : safeNext);
  }

  return (
    <AuthCard title="Sign in">
      <ErrorNotice error={error} />
      <form onSubmit={submit}>
        <div className="field"><label htmlFor="email">Email</label>
          <input id="email" type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} /></div>
        <div className="field"><label htmlFor="password">Password</label>
          <input id="password" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} /></div>
        <button className="primary" disabled={busy} style={{ width: "100%", justifyContent: "center" }}>{busy ? "Signing in…" : "Sign in"}</button>
      </form>
      <div className="foot"><Link href="/forgot-password">Forgot password?</Link> · New here? <Link href="/register">Create an account</Link></div>
    </AuthCard>
  );
}

export default function Page() {
  return <Suspense><LoginForm /></Suspense>;
}
