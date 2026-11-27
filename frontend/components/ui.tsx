"use client";

import { useCallback, useEffect, useState, type ReactNode } from "react";
import { ApiError } from "@/lib/api";
import { formatMoney, isNegative, STATUS_LABELS } from "@/lib/format";

export function useLoad<T>(loader: () => Promise<T>, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<ApiError | Error | null>(null);
  const [loading, setLoading] = useState(true);
  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await loader());
    } catch (e) {
      setError(e as Error);
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  useEffect(() => {
    reload();
  }, [reload]);
  return { data, error, loading, reload, setData };
}

export function Money({ value, currency, strong }: { value?: string | null; currency?: string; strong?: boolean }) {
  const text = formatMoney(value, currency);
  const style = isNegative(value) ? { color: "var(--danger)" } : undefined;
  return strong ? <strong style={style}>{text}</strong> : <span style={style}>{text}</span>;
}

export function StatusBadge({ status }: { status: string }) {
  return <span className={`badge ${status}`}>{STATUS_LABELS[status] ?? status}</span>;
}

export function Badge({ kind, children }: { kind?: string; children: ReactNode }) {
  return <span className={`badge ${kind ?? ""}`}>{children}</span>;
}

export function Notice({ kind = "info", children }: { kind?: "info" | "ok" | "warn" | "error"; children: ReactNode }) {
  return <div className={`notice ${kind}`} role={kind === "error" ? "alert" : "status"}>{children}</div>;
}

export function ErrorNotice({ error }: { error: unknown }) {
  if (!error) return null;
  const e = error as ApiError;
  const details = e.details as any;
  return (
    <Notice kind="error">
      {e.message || "Something went wrong"}
      {details?.missing && <div className="small">Missing: {details.missing.join(", ")}</div>}
      {details?.error_rows && <div className="small">Rows: {details.error_rows.join(", ")}</div>}
    </Notice>
  );
}

export function Loading() {
  return <div className="empty">Loading…</div>;
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="empty">{children}</div>;
}

export function AuthCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="auth">
      <div className="auth-card">
        <div className="brand">Vitta<span>synx</span></div>
        <h1>{title}</h1>
        {children}
      </div>
    </div>
  );
}

/** Wraps an async action with busy and error state, so forms can't double-submit. */
export function useAction() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const run = useCallback(async <T,>(fn: () => Promise<T>): Promise<T | undefined> => {
    setBusy(true);
    setError(null);
    try {
      return await fn();
    } catch (e) {
      setError(e);
      return undefined;
    } finally {
      setBusy(false);
    }
  }, []);
  return { busy, error, setError, run };
}
