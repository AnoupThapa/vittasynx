"use client";

import Link from "next/link";
import { useParams, usePathname, useRouter } from "next/navigation";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { apiGet, apiSend } from "@/lib/api";
import { canRole, OrgContext, type Me } from "@/components/OrgContext";
import { Loading, Notice } from "@/components/ui";

const NAV: { group: string; items: { href: string; label: string; needs?: string }[] }[] = [
  { group: "Receivables", items: [
    { href: "dashboard", label: "Dashboard" },
    { href: "invoices", label: "Invoices" },
    { href: "customers", label: "Customers" },
    { href: "payments", label: "Payments" },
    { href: "credit-notes", label: "Credit notes" },
  ] },
  { group: "Data", items: [
    { href: "imports", label: "Imports" },
    { href: "amendments", label: "Amendments" },
    { href: "reports", label: "Reports & exports" },
  ] },
  { group: "Organisation", items: [
    { href: "members", label: "Members" },
    { href: "audit", label: "Audit log", needs: "view_audit" },
    { href: "settings", label: "Settings" },
  ] },
];

export default function OrgLayout({ children }: { children: ReactNode }) {
  const { orgId } = useParams<{ orgId: string }>();
  const pathname = usePathname();
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  const [asAt, setAsAt] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiGet<Me>("/auth/me").then(setMe).catch((e) => setError(e.message));
  }, []);

  const org = me?.organisations.find((o) => o.id === orgId);
  const ctx = useMemo(() => (me && org ? {
    me, org, asAt, setAsAt, base: `/orgs/${org.id}`, can: (a: any) => canRole(org.role, a),
  } : null), [me, org, asAt]);

  if (error) return <div className="main"><Notice kind="error">{error}</Notice></div>;
  if (!me) return <Loading />;
  if (!org || !ctx) {
    return <div className="main"><Notice kind="error">Organisation not found or you are not a member.</Notice>
      <Link href="/orgs">Choose an organisation</Link></div>;
  }
  const needsMfa = me.mfa_required_for_privileged && ["owner", "admin"].includes(org.role) && !me.user.mfa_enabled;

  async function logout() {
    await apiSend("POST", "/auth/logout").catch(() => undefined);
    router.push("/login");
  }

  return (
    <OrgContext.Provider value={ctx}>
      <div className="app">
        <aside className="sidebar">
          <div className="brand">Vitta<span>synx</span></div>
          <div className="org-switch">
            <select aria-label="Organisation" value={org.id}
              onChange={(e) => (e.target.value === "__new" ? router.push("/orgs") : router.push(`/o/${e.target.value}/dashboard`))}>
              {me.organisations.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
              <option value="__new">+ Other / new organisation</option>
            </select>
          </div>
          <nav className="nav">
            {NAV.map((g) => (
              <div key={g.group}>
                <div className="nav-group">{g.group}</div>
                {g.items.filter((i) => !i.needs || canRole(org.role, i.needs as any)).map((i) => {
                  const href = `/o/${org.id}/${i.href}`;
                  return <Link key={i.href} href={href} className={pathname.startsWith(href) ? "active" : ""}>{i.label}</Link>;
                })}
              </div>
            ))}
          </nav>
          <div className="sidebar-foot">
            <div style={{ color: "#fff" }}>{me.user.full_name}</div>
            <div>{org.role_label}</div>
            <div style={{ marginTop: 8, display: "flex", gap: 12 }}>
              <Link href="/security" style={{ color: "#c9d1dc" }}>Security</Link>
              <button onClick={logout}>Sign out</button>
            </div>
          </div>
        </aside>
        <main className="main">
          {needsMfa ? (
            <Notice kind="warn">
              Owners and Administrators must turn on two-factor authentication before working with financial data.{" "}
              <Link href="/security">Set it up now</Link>.
            </Notice>
          ) : children}
        </main>
      </div>
    </OrgContext.Provider>
  );
}
