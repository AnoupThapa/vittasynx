"use client";

import { createContext, useContext } from "react";

export type OrgInfo = {
  id: string;
  name: string;
  currency: string;
  timezone: string;
  role: string;
  role_label: string;
};

export type Me = {
  user: { id: string; email: string; full_name: string; email_verified: boolean; mfa_enabled: boolean };
  organisations: OrgInfo[];
  mfa_required_for_privileged: boolean;
};

export type OrgCtx = {
  me: Me;
  org: OrgInfo;
  asAt: string; // "" = today in the organisation's timezone (resolved by the server)
  setAsAt: (v: string) => void;
  base: string; // API base path for this org, e.g. /orgs/<id>
  /** UI convenience only: hides actions the role cannot perform. The backend enforces permissions. */
  can: (action: Action) => boolean;
};

export type Action =
  | "export" | "manage_customers" | "import" | "approve_amendment" | "record_payment" | "confirm_allocation"
  | "reverse_allocation" | "manage_credits_and_status" | "view_audit" | "manage_members" | "manage_settings"
  | "owner_actions";

const ALL: Action[] = ["export", "manage_customers", "import", "approve_amendment", "record_payment",
  "confirm_allocation", "reverse_allocation", "manage_credits_and_status", "view_audit", "manage_members",
  "manage_settings", "owner_actions"];
const FINANCE = ALL.filter((a) => !["manage_members", "manage_settings", "owner_actions"].includes(a));
const ROLE_ACTIONS: Record<string, Action[]> = {
  owner: ALL,
  admin: ALL.filter((a) => a !== "owner_actions"),
  finance_manager: FINANCE,
  ar_officer: ["export", "manage_customers", "import", "record_payment", "confirm_allocation"],
  read_only: [],
};

export function canRole(role: string, action: Action): boolean {
  return (ROLE_ACTIONS[role] ?? []).includes(action);
}

export const OrgContext = createContext<OrgCtx | null>(null);

export function useOrg(): OrgCtx {
  const ctx = useContext(OrgContext);
  if (!ctx) throw new Error("useOrg must be used inside an organisation page");
  return ctx;
}

export function asAtQuery(asAt: string, prefix = "?"): string {
  return asAt ? `${prefix}as_at=${asAt}` : "";
}
