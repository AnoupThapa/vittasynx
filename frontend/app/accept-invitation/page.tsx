"use client";

import Link from "next/link";
import { Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { apiSend } from "@/lib/api";
import { AuthCard, ErrorNotice, useAction } from "@/components/ui";

function Accept() {
  const token = useSearchParams().get("token") || "";
  const router = useRouter();
  const { busy, error, run } = useAction();
  async function accept() {
    const org = await run(() => apiSend("POST", "/invitations/accept", { token }));
    if (org) router.push(`/o/${org.id}/dashboard`);
  }
  return (
    <AuthCard title="Join an organisation">
      <p className="muted">Sign in with the email address the invitation was sent to, then accept it.</p>
      <ErrorNotice error={error} />
      <div className="toolbar">
        <button className="primary" disabled={busy || !token} onClick={accept}>Accept invitation</button>
        <Link href={`/login?next=${encodeURIComponent(`/accept-invitation?token=${token}`)}`}>Sign in first</Link>
      </div>
    </AuthCard>
  );
}

export default function Page() {
  return <Suspense><Accept /></Suspense>;
}
