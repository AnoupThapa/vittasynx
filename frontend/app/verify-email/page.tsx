"use client";

import Link from "next/link";
import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { apiSend } from "@/lib/api";
import { AuthCard, ErrorNotice, Notice } from "@/components/ui";

function Verify() {
  const token = useSearchParams().get("token") || "";
  const [state, setState] = useState<"working" | "ok" | "error">("working");
  const [error, setError] = useState<unknown>(null);
  useEffect(() => {
    apiSend("POST", "/auth/verify-email", { token }).then(() => setState("ok")).catch((e) => { setError(e); setState("error"); });
  }, [token]);
  return (
    <AuthCard title="Email verification">
      {state === "working" && <p className="muted">Verifying…</p>}
      {state === "ok" && <Notice kind="ok">Your email address is verified.</Notice>}
      {state === "error" && <ErrorNotice error={error} />}
      <Link href="/">Continue</Link>
    </AuthCard>
  );
}

export default function Page() {
  return <Suspense><Verify /></Suspense>;
}
